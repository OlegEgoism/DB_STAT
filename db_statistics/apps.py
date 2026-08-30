from threading import Timer

from django.apps import AppConfig
from django.db import OperationalError, ProgrammingError
from django.db.backends.signals import connection_created


def _enable_sqlite_wal(sender, connection, **kwargs):
    """Включает WAL для SQLite на каждом новом соединении.

    Служебная БД приложения — единственный SQLite-файл, к которому пишут и
    поток запроса, и до 4 потоков MAINTENANCE_JOB_EXECUTOR (см. db/settings.py),
    а в многопроцессном WSGI-развёртывании — ещё и другие воркеры. WAL позволяет
    читателям не блокироваться на писателях и заметно снижает частоту ошибок
    "database is locked" по сравнению с журналом по умолчанию.
    """
    if connection.vendor != "sqlite":
        return
    with connection.cursor() as cursor:
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("PRAGMA busy_timeout=20000;")


class DbStatisticsConfig(AppConfig):
    name = "db_statistics"
    verbose_name = "DB STAT"

    def ready(self):
        """Запускает сохранённые задачи после полной инициализации Django"""
        connection_created.connect(_enable_sqlite_wal)

        def submit_queued_jobs():
            from db_statistics.models import MaintenanceJob
            from db_statistics.view_helpers import _submit_maintenance_job

            try:
                # Задачи, оставшиеся в статусе "running" после аварийного
                # завершения процесса (падение, деплой, OOM), иначе провисят
                # в этом статусе бесконечно — атомарный захват в
                # _run_maintenance_operation защищает только от повторного
                # запуска уже выполняющейся задачи, а не от восстановления
                # прерванной.
                MaintenanceJob.objects.filter(status="running").update(
                    status="queued",
                    message="Операция восстановлена после перезапуска",
                    started=None,
                )
                job_ids = list(MaintenanceJob.objects.filter(status="queued").values_list("pk", flat=True))
            except (OperationalError, ProgrammingError):
                return
            for job_id in job_ids:
                _submit_maintenance_job(job_id)

        Timer(0.5, submit_queued_jobs).start()
