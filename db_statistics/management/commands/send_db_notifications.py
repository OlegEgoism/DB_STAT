from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand, CommandError

from db_statistics.services.notifications import process_due_notifications


class Command(BaseCommand):
    help = "Проверяет DBNotification и отправляет email-уведомления пользователям."

    def add_arguments(self, parser):
        parser.add_argument("--force", action="store_true", help="Игнорировать interval_update и проверить все активные уведомления.")
        parser.add_argument("--test-email", help="Отправить тестовое письмо на указанный email без проверки DBNotification.")
        parser.add_argument("--test-subject", default="[DB-STAT] Тестовое уведомление", help="Тема тестового письма.")
        parser.add_argument("--test-message", default="Это тестовое письмо DB-STAT. Настройки email работают корректно.", help="Текст тестового письма.")

    def handle(self, *args, **options):
        if options["test_email"]:
            sent_count = send_mail(options["test_subject"], options["test_message"], settings.DEFAULT_FROM_EMAIL, [options["test_email"]], fail_silently=False)
            if sent_count != 1:
                raise CommandError("Тестовое письмо не было отправлено")
            self.stdout.write(self.style.SUCCESS(f"test_email_sent=1 recipient={options['test_email']} backend={settings.EMAIL_BACKEND}"))
            return

        stats = process_due_notifications(force=options["force"])
        self.stdout.write(self.style.SUCCESS(f"checked={stats['checked']} sent={stats['sent']} skipped={stats['skipped']} failed={stats['failed']}"))
