import os
import sys
import threading
import time

from django.db import close_old_connections
from django.utils import timezone

from db_statistics.models import DBSegmentHealthCheckSetting
from db_statistics.services.segments import load_segments_health, write_segment_health_audit

CONNECTION_TIMEOUT_SECONDS = 5

_WORKER_STARTED = False


def _run_due_checks():
    now = timezone.now()
    settings = DBSegmentHealthCheckSetting.objects.select_related("connection").filter(is_active=True, connection__is_active=True).filter(next_run_at__isnull=True) | DBSegmentHealthCheckSetting.objects.select_related("connection").filter(is_active=True, connection__is_active=True, next_run_at__lte=now)
    for setting in settings.distinct():
        db_connection = setting.connection
        try:
            result = load_segments_health(db_connection, _connection_kwargs)
        except Exception as exc:
            write_segment_health_audit(db_connection, error=exc)
        else:
            write_segment_health_audit(db_connection, result=result)
        finally:
            finished_at = timezone.now()
            setting.last_run_at = finished_at
            setting.next_run_at = finished_at + timezone.timedelta(minutes=max(setting.interval_minutes, 1))
            setting.save(update_fields=["last_run_at", "next_run_at", "updated"])


def _connection_kwargs(host, port, database, username, password, ssl=True):
    return {
        "host": host,
        "port": port,
        "dbname": database,
        "user": username,
        "password": password,
        "connect_timeout": CONNECTION_TIMEOUT_SECONDS,
        "sslmode": "prefer" if ssl else "disable",
    }


def _worker_loop(poll_seconds):
    while True:
        close_old_connections()
        try:
            _run_due_checks()
        finally:
            close_old_connections()
        time.sleep(poll_seconds)


def start_segment_health_worker():
    global _WORKER_STARTED
    if _WORKER_STARTED:
        return
    if os.environ.get("RUN_MAIN") == "false":
        return
    if os.environ.get("SEGMENT_HEALTH_WORKER_ENABLED", "1").strip().lower() in {"0", "false", "no", "off"}:
        return
    if len(sys.argv) > 1 and sys.argv[1] in {"makemigrations", "migrate", "collectstatic", "test", "shell", "dbshell", "check"}:
        return
    _WORKER_STARTED = True
    poll_seconds = int(os.environ.get("SEGMENT_HEALTH_WORKER_POLL_SECONDS", "60"))
    thread = threading.Thread(target=_worker_loop, args=(poll_seconds,), name="segment-health-worker", daemon=True)
    thread.start()
