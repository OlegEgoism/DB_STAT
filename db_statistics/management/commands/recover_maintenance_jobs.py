from django.core.management.base import BaseCommand

from db_statistics.job_locks import job_owner_alive
from db_statistics.models import MaintenanceJob, ReportJob


class Command(BaseCommand):
    help = "Возвращает осиротевшие фоновые операции и отчёты в статус «В очереди». Постановку на выполнение делает стартовый sweep (db_statistics/apps.py)"

    def handle(self, *args, **options):
        # Сбрасываем только задачи, чей выполняющий процесс погиб (lock-файл свободен, см. job_locks.py).
        # Так команду можно безопасно запускать и при работающем сервере: живые задачи не трогаются.
        # Команда только меняет статусы и завершается: не ставит задачи в пул потоков.
        # Иначе при старте контейнера выход процесса ждал бы завершения восстановленных
        # задач (например, VACUUM FULL) и gunicorn не запускался бы. Постановку делает
        # _resubmit_queued_jobs при старте каждого процесса (см. apps.py).
        recovered = 0
        for job in MaintenanceJob.objects.filter(status="running"):
            if not job_owner_alive(job.pk):
                recovered += MaintenanceJob.objects.filter(pk=job.pk, status="running").update(status="queued", message="Операция восстановлена после перезапуска", started=None)
        recovered_reports = 0
        for report in ReportJob.objects.filter(status="running"):
            if not job_owner_alive(report.pk):
                recovered_reports += ReportJob.objects.filter(pk=report.pk, status="running").update(status="queued", message="Формирование отчёта восстановлено после перезапуска", started=None)
        self.stdout.write(self.style.SUCCESS(f"Восстановлено задач обслуживания: {recovered}, отчётов: {recovered_reports}"))
