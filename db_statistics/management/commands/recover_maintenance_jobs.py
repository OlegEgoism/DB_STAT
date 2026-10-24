from django.core.management.base import BaseCommand

from db_statistics.models import MaintenanceJob, ReportJob
from db_statistics.views.maintenance import _submit_maintenance_job
from db_statistics.views.reports import _submit_report_job


class Command(BaseCommand):
    help = "Возвращает прерванные фоновые операции и отчёты в очередь и сразу перезапускает их"

    def handle(self, *args, **options):
        # Единственное место, где статус «Выполняется» сбрасывается в «В очереди».
        # Вызывается один раз до старта gunicorn (docker-entrypoint.sh) или
        # вручную, когда процесс уже не работает. Сбрасывать статусы из
        # каждого воркера нельзя: см. комментарий в db_statistics/apps.py.
        # _run_maintenance_operation и _run_report_job захватывают задачу
        # атомарно через status="queued", поэтому даже повторная постановка
        # не приводит к двойному выполнению.
        job_ids = list(MaintenanceJob.objects.filter(status="running").values_list("pk", flat=True))
        recovered = MaintenanceJob.objects.filter(pk__in=job_ids).update(status="queued", message="Операция восстановлена после перезапуска", started=None)
        report_job_ids = list(ReportJob.objects.filter(status="running").values_list("pk", flat=True))
        recovered_reports = ReportJob.objects.filter(pk__in=report_job_ids).update(status="queued", message="Формирование отчёта восстановлено после перезапуска", started=None)
        for job_id in job_ids:
            _submit_maintenance_job(job_id)
        for job_id in report_job_ids:
            _submit_report_job(job_id)
        self.stdout.write(self.style.SUCCESS(f"Восстановлено задач обслуживания: {recovered}, отчётов: {recovered_reports}"))
