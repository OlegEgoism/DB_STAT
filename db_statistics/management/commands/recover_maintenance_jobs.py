from django.core.management.base import BaseCommand

from db_statistics.models import MaintenanceJob


class Command(BaseCommand):
    help = "Возвращает прерванные фоновые операции обслуживания в очередь"

    def handle(self, *args, **options):
        recovered = MaintenanceJob.objects.filter(status="running").update(
            status="queued",
            message="Операция восстановлена после перезапуска",
            started=None,
        )
        self.stdout.write(self.style.SUCCESS(f"Восстановлено задач: {recovered}"))
