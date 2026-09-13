from django.core.management.base import BaseCommand

from db_statistics.models import MaintenanceJob
from db_statistics.views.maintenance import _submit_maintenance_job


class Command(BaseCommand):
    help = "Возвращает прерванные фоновые операции обслуживания в очередь и сразу перезапускает их"

    def handle(self, *args, **options):
        job_ids = list(MaintenanceJob.objects.filter(status="running").values_list("pk", flat=True))
        recovered = MaintenanceJob.objects.filter(pk__in=job_ids).update(status="queued", message="Операция восстановлена после перезапуска", started=None)
        # Called both from docker-entrypoint.sh before gunicorn starts (where
        # apps.py.ready()'s own startup sweep would otherwise pick these up a
        # moment later anyway) and as a standalone admin command against an
        # already-running process (which has no other trigger to resume
        # them). _run_maintenance_operation claims a job atomically via
        # status="queued" before running it, so a job submitted from both
        # places still only executes once.
        for job_id in job_ids:
            _submit_maintenance_job(job_id)
        self.stdout.write(self.style.SUCCESS(f"Восстановлено задач: {recovered}"))
