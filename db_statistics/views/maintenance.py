"""Background maintenance jobs (VACUUM/ANALYZE/EXPLAIN) and backend termination.

Split out of views/helpers.py (see its module docstring). Grouped together
because both are admin-triggered, audited actions against the target DB that
run through the connection pool.
"""

import logging
import time

import psycopg2
from django.conf import settings
from django.db import close_old_connections
from django.http import JsonResponse
from django.utils import timezone
from psycopg2 import sql

from db_statistics.models import DBConnection, MaintenanceJob
from db_statistics.views.audit import MAINTENANCE_OPERATION_LABELS, _backend_termination_audit_info, _maintenance_operation_audit_info, _write_audit
from db_statistics.views.auth import _current_db_user, _destructive_action_permission_error, _require_payload_connection
from db_statistics.views.helpers import _read_json_body
from db_statistics.views.pool import _fetch_db_row, _open_database_connection, _query_or_error, _safe_db_error_message

logger = logging.getLogger(__name__)


def _terminate_backend(request, *, require_active, invalid_pid_message, not_found_message, failed_message, success_message, audit_action_type, audit_label):
    """Общая логика для завершения активного запроса и завершения сессии.

    Различие между ними — это только SQL-условие `state = 'active'` (запрос
    обязан быть активным, сессию можно завершить в любом состоянии) и
    формулировки сообщений/аудита, поэтому текст сообщений передаётся
    вызывающей стороной, а не собирается здесь по шаблону (у "запроса" и
    "сессии" разный род в русском — "не найден"/"не найдена").
    """
    permission_error = _destructive_action_permission_error(request)
    if permission_error:
        return permission_error
    payload = _read_json_body(request)
    db_connection, error_response = _require_payload_connection(request, payload)
    if error_response:
        return error_response

    try:
        pid = int(payload.get("pid"))
        if pid <= 0:
            raise ValueError
    except (TypeError, ValueError):
        return JsonResponse({"ok": False, "message": invalid_pid_message}, status=400)

    active_clause = "\n          AND activity.state = 'active'" if require_active else ""
    terminate_query = f"""
        SELECT
            pg_catalog.pg_terminate_backend(activity.pid),
            activity.pid,
            activity.usename,
            activity.datname,
            activity.application_name,
            activity.client_addr,
            activity.client_port,
            activity.state,
            activity.backend_type,
            activity.backend_start,
            activity.xact_start,
            activity.query_start,
            activity.state_change,
            activity.wait_event_type,
            activity.wait_event,
            now() - activity.backend_start AS session_duration,
            CASE WHEN activity.query_start IS NULL THEN NULL ELSE now() - activity.query_start END AS query_duration,
            activity.query
        FROM pg_catalog.pg_stat_activity AS activity
        WHERE activity.pid = %s
          AND activity.pid <> pg_backend_pid(){active_clause};
    """
    row, error_response = _query_or_error(f"Не удалось завершить процесс с PID {pid}", lambda: _fetch_db_row(db_connection, terminate_query, [pid]))
    if error_response:
        return error_response

    if not row:
        return JsonResponse({"ok": False, "message": not_found_message(pid)}, status=404)
    if not row[0]:
        return JsonResponse({"ok": False, "message": failed_message(pid)}, status=409)

    _write_audit(audit_action_type, _backend_termination_audit_info(audit_label, db_connection, row), db_user=_current_db_user(request))
    return JsonResponse({"ok": True, "message": success_message(pid), "pid": pid})


def _serialize_maintenance_job(job):
    """Преобразует сохранённую задачу в безопасный ответ API."""
    return {
        "id": str(job.pk),
        "connection_id": job.connection_id,
        "connection_name": job.connection.name,
        "username": job.user.login if job.user else "—",
        "status": job.status,
        "operation": job.operation,
        "schema_name": job.schema_name,
        "table_name": job.table_name,
        "message": job.message,
        "details": job.details,
        "statistics": job.statistics,
        "duration_seconds": job.duration_seconds,
        "created": job.created.isoformat(),
        "started": job.started.isoformat() if job.started else None,
        "finished": job.finished.isoformat() if job.finished else None,
    }


def _submit_maintenance_job(job_id):
    settings.MAINTENANCE_JOB_EXECUTOR.submit(_run_maintenance_operation, str(job_id))


def _run_maintenance_operation(job_id):
    """Выполняет VACUUM/ANALYZE/EXPLAIN ANALYZE и обновляет состояние задачи."""
    close_old_connections()
    claimed = MaintenanceJob.objects.filter(pk=job_id, status="queued").update(status="running", message="Операция выполняется", started=timezone.now())
    if not claimed:
        close_old_connections()
        return
    job = MaintenanceJob.objects.select_related("connection", "user").get(pk=job_id)
    connection_id = job.connection_id
    schema_name = job.schema_name
    table_name = job.table_name
    operation = job.operation
    username = job.user.login if job.user else "system"
    db_connection = None
    started_at = time.monotonic()
    try:
        db_connection = DBConnection.objects.get(pk=connection_id)
        table_identifier = sql.Identifier(schema_name, table_name)
        if operation in {"vacuum", "vacuum_full"}:
            statement = sql.SQL("VACUUM {mode} {table}").format(mode=sql.SQL("FULL") if operation == "vacuum_full" else sql.SQL(""), table=table_identifier)
        elif operation == "analyze":
            statement = sql.SQL("ANALYZE {table}").format(table=table_identifier)
        else:
            statement = sql.SQL("EXPLAIN (ANALYZE, BUFFERS, VERBOSE, FORMAT TEXT) SELECT * FROM {table}").format(table=table_identifier)
        # VACUUM запрещён внутри транзакции, поэтому autocommit включается
        # сразу после открытия соединения, до выполнения запроса.
        with _open_database_connection(db_connection) as connection:
            connection.autocommit = True
            with connection.cursor() as cursor:
                cursor.execute(statement)
                details = [str(row[0]) for row in cursor.fetchmany(500)] if operation == "explain_analyze" else []
                # После VACUUM принудительно обновляем оценки планировщика.
                # В Greenplum/Greengage значения pg_stat_user_tables на
                # coordinator без ANALYZE могут оставаться устаревшими.
                if operation in {"vacuum", "vacuum_full"}:
                    cursor.execute(sql.SQL("ANALYZE {table}").format(table=table_identifier))
                cursor.execute(
                    """
                    SELECT
                        COALESCE(n_live_tup, 0)::bigint,
                        COALESCE(n_dead_tup, 0)::bigint,
                        last_vacuum,
                        last_autovacuum,
                        last_analyze,
                        last_autoanalyze
                    FROM pg_catalog.pg_stat_user_tables
                    WHERE schemaname = %s AND relname = %s
                    """,
                    [schema_name, table_name],
                )
                statistics_row = cursor.fetchone()
                statistics = (
                    {
                        "live_rows": int(statistics_row[0]),
                        "dead_rows": int(statistics_row[1]),
                        "last_vacuum": max(filter(None, (statistics_row[2], statistics_row[3])), default=None).isoformat() if any((statistics_row[2], statistics_row[3])) else None,
                        "last_analyze": max(filter(None, (statistics_row[4], statistics_row[5])), default=None).isoformat() if any((statistics_row[4], statistics_row[5])) else None,
                        "is_estimate": True,
                    }
                    if statistics_row
                    else None
                )
    except psycopg2.Error as exc:
        # Routed through _safe_db_error_message (like every other DB-facing
        # endpoint) instead of the raw str(exc): the admin who owns this job
        # can still see the full driver error in the server log this logs to.
        action_description = f"Не удалось выполнить {MAINTENANCE_OPERATION_LABELS.get(operation, operation.upper())} для {schema_name}.{table_name}"
        result = {"status": "failed", "message": _safe_db_error_message(action_description, exc), "details": []}
    except Exception:
        # This runs on a background thread (ThreadPoolExecutor) with no caller
        # waiting on the Future — anything other than psycopg2.Error used to
        # propagate into the discarded Future and vanish with no log line and
        # no status update, leaving the job stuck in "running" forever (only
        # apps.py's startup recovery would ever notice). Catch-all here so a
        # bug always still marks the job failed and gets logged.
        logger.exception("Непредвиденная ошибка при выполнении задачи обслуживания job_id=%s", job_id)
        result = {"status": "failed", "message": "Внутренняя ошибка при выполнении операции. Подробности см. в журнале сервера приложения", "details": []}
    else:
        result = {"status": "completed", "message": "Операция успешно завершена", "details": details, "statistics": statistics}
    result["duration_seconds"] = round(time.monotonic() - started_at, 3)

    MaintenanceJob.objects.filter(pk=job_id).update(status=result["status"], message=result["message"], details=result.get("details", []), statistics=result.get("statistics"), duration_seconds=result["duration_seconds"], finished=timezone.now())

    if db_connection is not None:
        audit_info = _maintenance_operation_audit_info(operation, db_connection, schema_name, table_name, ("успешно завершено" if result["status"] == "completed" else "ошибка выполнения"), result.get("message") if result["status"] == "failed" else None)
    else:
        audit_info = "; ".join([f"Действие: {MAINTENANCE_OPERATION_LABELS.get(operation, operation.upper())}", f"ID подключения: {connection_id}", f"Схема: {schema_name}", f"Таблица: {table_name}", "Результат: ошибка выполнения", f"Ошибка: {result['message']}"])
    _write_audit(operation, audit_info, username=username)
    close_old_connections()
