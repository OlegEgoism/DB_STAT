from django.core.management.base import BaseCommand

from db_statistics.services.notifications import process_due_notifications


class Command(BaseCommand):
    help = "Проверяет DBNotification и отправляет email-уведомления пользователям."

    def add_arguments(self, parser):
        parser.add_argument("--force", action="store_true", help="Игнорировать interval_update и проверить все активные уведомления.")

    def handle(self, *args, **options):
        stats = process_due_notifications(force=options["force"])
        self.stdout.write(self.style.SUCCESS(f"checked={stats['checked']} sent={stats['sent']} skipped={stats['skipped']} failed={stats['failed']}"))
