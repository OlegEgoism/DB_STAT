import os
import sys
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
        from db_statistics import checks  # noqa: F401 — регистрирует проверки через @register()

        connection_created.connect(_enable_sqlite_wal)

        if _runs_background_sweep():
            Timer(0.5, _resubmit_queued_jobs).start()


def _runs_background_sweep():
    """Запускать ли стартовый sweep очереди в этом процессе.

    Sweep ставит задачи на выполнение, поэтому он нужен только серверным процессам: gunicorn
    и `manage.py runserver`. Одноразовые команды (`shell`, `createsuperuser`, `check` и другие)
    не должны запускать очередь: их процесс завершится, и задачи оборвутся на полпути.
    Тесты тоже не запускают очередь.
    """
    if _running_tests():
        return False
    argv = sys.argv
    if argv and os.path.basename(argv[0]) == "manage.py":
        return len(argv) > 1 and argv[1] == "runserver"
    return True


def _running_tests():
    """Истина, когда приложение запущено командой `manage.py test`.

    Фоновый запуск очереди при импорте приложения обращается к файлу БД из
    настроек, поэтому в тестах он не нужен и может задеть реальную базу.
    """
    return len(sys.argv) > 1 and sys.argv[1] == "test"


def _resubmit_queued_jobs():
    """Ставит на выполнение задачи, которые остались в статусе «В очереди».

    Здесь намеренно НЕТ сброса статуса «Выполняется» в «В очереди»: каждый
    процесс gunicorn (воркер) вызывает эту функцию при старте, и сброс
    «running» отнял бы задачу у воркера, который её сейчас выполняет, после
    чего она запустилась бы повторно. Восстановление прерванных задач
    выполняет только команда `recover_maintenance_jobs`, которую
    docker-entrypoint.sh запускает один раз до старта gunicorn.
    """
    from db_statistics.job_locks import job_owner_alive
    from db_statistics.models import MaintenanceJob, ReportJob
    from db_statistics.views.maintenance import _submit_maintenance_job
    from db_statistics.views.reports import _ensure_report_job_table, _submit_report_job

    try:
        _ensure_report_job_table()
        # Задача в статусе «Выполняется» сбрасывается в очередь, только если её выполняющий процесс
        # погиб: lock-файл свободен (см. db_statistics/job_locks.py). Живую задачу не трогаем.
        for job in MaintenanceJob.objects.filter(status="running"):
            if not job_owner_alive(job.pk):
                MaintenanceJob.objects.filter(pk=job.pk, status="running").update(status="queued", message="Операция восстановлена после падения процесса", started=None)
        for job in ReportJob.objects.filter(status="running"):
            if not job_owner_alive(job.pk):
                ReportJob.objects.filter(pk=job.pk, status="running").update(status="queued", message="Формирование отчёта восстановлено после падения процесса", started=None)
        job_ids = list(MaintenanceJob.objects.filter(status="queued").values_list("pk", flat=True))
        report_job_ids = list(ReportJob.objects.filter(status="queued").values_list("pk", flat=True))
    except (OperationalError, ProgrammingError):
        return
    for job_id in job_ids:
        _submit_maintenance_job(job_id)
    for job_id in report_job_ids:
        _submit_report_job(job_id)
