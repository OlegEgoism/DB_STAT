from django.core.management.base import BaseCommand

from db_statistics.models import MaintenanceJob, ReportJob


class Command(BaseCommand):
    help = "Возвращает прерванные фоновые операции и отчёты в статус «В очереди». Постановку на выполнение делает стартовый sweep (db_statistics/apps.py)"

    def handle(self, *args, **options):
        # Единственное место, где статус «Выполняется» сбрасывается в «В очереди».
        # Команда только меняет статусы и завершается: не ставит задачи в пул потоков.
        # Иначе при старте контейнера выход процесса ждал бы завершения восстановленных
        # задач (например, VACUUM FULL) и gunicorn не запускался бы. Постановку делает
        # _resubmit_queued_jobs при старте каждого процесса (см. apps.py); захват задачи
        # атомарный (status="queued"), поэтому повторная постановка не даёт двойного запуска.
        recovered = MaintenanceJob.objects.filter(status="running").update(status="queued", message="Операция восстановлена после перезапуска", started=None)
        recovered_reports = ReportJob.objects.filter(status="running").update(status="queued", message="Формирование отчёта восстановлено после перезапуска", started=None)
        self.stdout.write(self.style.SUCCESS(f"Восстановлено задач обслуживания: {recovered}, отчётов: {recovered_reports}"))
