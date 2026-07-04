from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

import psycopg2
from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone

from db_statistics.models import DBNotification
from db_statistics.views import _connection_kwargs, _format_bytes


@dataclass(frozen=True)
class NotificationEvent:
    title: str
    details: list[str]


SEGMENT_SQL = """
    SELECT content, role, preferred_role, mode, status, hostname, address, port
    FROM gp_segment_configuration
    WHERE status <> 'u' OR role <> preferred_role
    ORDER BY content, role, hostname;
"""

TEMP_TABLES_SQL = """
    SELECT
        namespace.nspname AS schema_name,
        relation.relname AS table_name,
        pg_total_relation_size(relation.oid)::bigint AS size_bytes
    FROM pg_catalog.pg_class AS relation
    JOIN pg_catalog.pg_namespace AS namespace
        ON namespace.oid = relation.relnamespace
    WHERE relation.relpersistence = 't' OR namespace.nspname LIKE 'pg_temp_%'
    ORDER BY size_bytes DESC, schema_name, table_name
    LIMIT 20;
"""

ACTIVE_QUERIES_SQL = """
    SELECT pid, usename, GREATEST(now() - query_start, INTERVAL '0 seconds') AS duration, query
    FROM pg_catalog.pg_stat_activity
    WHERE state = 'active'
      AND pid <> pg_backend_pid()
      AND query_start IS NOT NULL
      AND EXTRACT(EPOCH FROM GREATEST(now() - query_start, INTERVAL '0 seconds')) >= %s
    ORDER BY duration DESC
    LIMIT 20;
"""

BLOCKING_LOCKS_SQL = """
    SELECT
        blocked.pid AS blocked_pid,
        blocked.usename AS blocked_user,
        GREATEST(now() - blocked.query_start, INTERVAL '0 seconds') AS blocked_duration,
        blocked.query AS blocked_query,
        blocker.pid AS blocker_pid,
        blocker.usename AS blocker_user
    FROM pg_catalog.pg_locks AS blocked_locks
    JOIN pg_catalog.pg_stat_activity AS blocked ON blocked.pid = blocked_locks.pid
    JOIN pg_catalog.pg_locks AS blocker_locks
        ON blocker_locks.locktype = blocked_locks.locktype
       AND blocker_locks.database IS NOT DISTINCT FROM blocked_locks.database
       AND blocker_locks.relation IS NOT DISTINCT FROM blocked_locks.relation
       AND blocker_locks.page IS NOT DISTINCT FROM blocked_locks.page
       AND blocker_locks.tuple IS NOT DISTINCT FROM blocked_locks.tuple
       AND blocker_locks.virtualxid IS NOT DISTINCT FROM blocked_locks.virtualxid
       AND blocker_locks.transactionid IS NOT DISTINCT FROM blocked_locks.transactionid
       AND blocker_locks.classid IS NOT DISTINCT FROM blocked_locks.classid
       AND blocker_locks.objid IS NOT DISTINCT FROM blocked_locks.objid
       AND blocker_locks.objsubid IS NOT DISTINCT FROM blocked_locks.objsubid
       AND blocker_locks.pid <> blocked_locks.pid
    JOIN pg_catalog.pg_stat_activity AS blocker ON blocker.pid = blocker_locks.pid
    WHERE NOT blocked_locks.granted
      AND blocker_locks.granted
      AND blocked.query_start IS NOT NULL
      AND EXTRACT(EPOCH FROM GREATEST(now() - blocked.query_start, INTERVAL '0 seconds')) >= %s
    ORDER BY blocked_duration DESC
    LIMIT 20;
"""

IDLE_TRANSACTIONS_SQL = """
    SELECT pid, usename, application_name, GREATEST(now() - xact_start, INTERVAL '0 seconds') AS transaction_duration, query
    FROM pg_catalog.pg_stat_activity
    WHERE state = 'idle in transaction'
      AND xact_start IS NOT NULL
      AND EXTRACT(EPOCH FROM GREATEST(now() - xact_start, INTERVAL '0 seconds')) >= %s
    ORDER BY transaction_duration DESC
    LIMIT 20;
"""


def _should_run(notification: DBNotification, now):
    if not notification.last_checked:
        return True
    elapsed = now - notification.last_checked
    return elapsed.total_seconds() >= notification.interval_update * 60


def _short_sql(value: str, limit: int = 300) -> str:
    text = " ".join(str(value or "").split())
    return text if len(text) <= limit else f"{text[:limit]}…"


def _collect_events(notification: DBNotification) -> list[NotificationEvent]:
    connection = notification.connection
    events: list[NotificationEvent] = []
    with psycopg2.connect(**_connection_kwargs(connection.host, connection.port, connection.database, connection.username, connection.get_password())) as db:
        with db.cursor() as cursor:
            if notification.segment_monitor:
                try:
                    cursor.execute(SEGMENT_SQL)
                    rows = cursor.fetchall()
                except psycopg2.Error as exc:
                    rows = []
                    if connection.db_type == "Greenplum":
                        raise exc
                if rows:
                    details = [f"content={r[0]}, role={r[1]}, preferred={r[2]}, mode={r[3]}, status={r[4]}, host={r[5] or r[6]}:{r[7]}" for r in rows]
                    events.append(NotificationEvent("Проблемы сегментов Greenplum", details))

            if notification.temp_tables_monitor:
                cursor.execute(TEMP_TABLES_SQL)
                rows = cursor.fetchall()
                if rows:
                    details = [f"{r[0]}.{r[1]} — {_format_bytes(int(r[2] or 0))}" for r in rows]
                    events.append(NotificationEvent("Обнаружены временные таблицы", details))

            if notification.query_monitor and notification.query_threshold:
                cursor.execute(ACTIVE_QUERIES_SQL, [notification.query_threshold])
                rows = cursor.fetchall()
                if rows:
                    details = [f"pid={r[0]}, user={r[1] or '—'}, duration={str(r[2]).split('.')[0]}, sql={_short_sql(r[3])}" for r in rows]
                    events.append(NotificationEvent(f"Активные запросы дольше {notification.query_threshold} сек.", details))

            if notification.lock_monitor and notification.lock_threshold:
                cursor.execute(BLOCKING_LOCKS_SQL, [notification.lock_threshold])
                rows = cursor.fetchall()
                if rows:
                    details = [f"blocked_pid={r[0]}, blocked_user={r[1] or '—'}, duration={str(r[2]).split('.')[0]}, blocker_pid={r[4]}, blocker_user={r[5] or '—'}, sql={_short_sql(r[3])}" for r in rows]
                    events.append(NotificationEvent(f"Блокировки дольше {notification.lock_threshold} сек.", details))

            if notification.transaction_monitor and notification.transactions_threshold:
                cursor.execute(IDLE_TRANSACTIONS_SQL, [notification.transactions_threshold])
                rows = cursor.fetchall()
                if rows:
                    details = [f"pid={r[0]}, user={r[1] or '—'}, app={r[2] or '—'}, duration={str(r[3]).split('.')[0]}, sql={_short_sql(r[4])}" for r in rows]
                    events.append(NotificationEvent(f"Idle in transaction дольше {notification.transactions_threshold} сек.", details))
    return events


def _build_message(notification: DBNotification, events: Iterable[NotificationEvent]) -> tuple[str, str]:
    connection = notification.connection
    subject = f"[DB-STAT] Уведомление: {connection.name} / {connection.database}"
    lines = ["DB-STAT обнаружил события мониторинга.", "", f"Подключение: {connection.name}", f"База данных: {connection.database}", f"Хост: {connection.host}:{connection.port}", ""]
    for event in events:
        lines.append(event.title)
        lines.extend(f"- {detail}" for detail in event.details)
        lines.append("")
    return subject, "\n".join(lines).strip()


def process_due_notifications(*, force: bool = False) -> dict[str, int]:
    now = timezone.now()
    stats = {"checked": 0, "sent": 0, "skipped": 0, "failed": 0}
    notifications = DBNotification.objects.filter(is_active=True, connection__is_active=True).select_related("connection").prefetch_related("user")
    for notification in notifications:
        if not force and not _should_run(notification, now):
            stats["skipped"] += 1
            continue
        stats["checked"] += 1
        recipients = [user.email for user in notification.user.all() if user.is_active and user.email]
        if not recipients:
            notification.last_checked = now
            notification.last_error = "Нет активных получателей с email"
            notification.save(update_fields=["last_checked", "last_error", "updated"])
            stats["failed"] += 1
            continue
        try:
            events = _collect_events(notification)
            with transaction.atomic():
                notification.last_checked = now
                notification.last_error = ""
                if events:
                    subject, message = _build_message(notification, events)
                    send_mail(subject, message, getattr(settings, "DEFAULT_FROM_EMAIL", None), recipients, fail_silently=False)
                    notification.last_sent = now
                    stats["sent"] += 1
                notification.save(update_fields=["last_checked", "last_sent", "last_error", "updated"])
        except Exception as exc:
            notification.last_checked = now
            notification.last_error = str(exc)[:1000]
            notification.save(update_fields=["last_checked", "last_error", "updated"])
            stats["failed"] += 1
    return stats
