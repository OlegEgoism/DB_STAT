import os
import secrets

from django.core.management.base import BaseCommand, CommandError

from db_statistics.models import DBUser


class Command(BaseCommand):
    help = "Создаёт первоначального администратора, если пользователей ещё нет"

    def handle(self, *args, **options):
        if DBUser.objects.exists():
            self.stdout.write("Initial administrator already exists; skipping creation.")
            return

        login = os.getenv("INITIAL_ADMIN_LOGIN", "admin").strip()
        email = os.getenv("INITIAL_ADMIN_EMAIL", "admin@example.com").strip()
        configured_password = os.getenv("INITIAL_ADMIN_PASSWORD", "admin").strip()
        password = configured_password or secrets.token_urlsafe(18)
        if not login or not email:
            raise CommandError("INITIAL_ADMIN_LOGIN and INITIAL_ADMIN_EMAIL cannot be empty")

        DBUser.objects.create_superuser(login, email, password)
        self.stdout.write(self.style.SUCCESS(f"Initial administrator '{login}' created."))
        if configured_password:
            self.stdout.write("The password was read from INITIAL_ADMIN_PASSWORD.")
        else:
            self.stdout.write(self.style.WARNING(f"Generated one-time initial password: {password}\n" "Save it now: it will not be displayed again."))
