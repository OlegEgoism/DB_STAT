from threading import Timer

from django.apps import AppConfig
from django.db import OperationalError, ProgrammingError


class DbStatisticsConfig(AppConfig):
    name = "db_statistics"
    verbose_name = "DB STAT"

    def ready(self):
        """Запускает сохранённые задачи после полной инициализации Django."""
        def submit_queued_jobs():
            from db_statistics.models import MaintenanceJob
            from db_statistics.view_helpers import _submit_maintenance_job

            try:
                job_ids = list(MaintenanceJob.objects.filter(status="queued").values_list("pk", flat=True))
            except (OperationalError, ProgrammingError):
                return
            for job_id in job_ids:
                _submit_maintenance_job(job_id)

        Timer(0.5, submit_queued_jobs).start()
