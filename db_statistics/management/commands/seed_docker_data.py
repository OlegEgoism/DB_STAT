from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from db_statistics.models import DBUser


class Command(BaseCommand):
    help = "Creates initial users for the Docker image."

    def handle(self, *args, **options):
        user_model = get_user_model()
        superuser, created = user_model.objects.update_or_create(
            username="admin",
            defaults={"email": "", "is_staff": True, "is_superuser": True, "is_active": True},
        )
        superuser.set_password("admin")
        superuser.save(update_fields=["password", "email", "is_staff", "is_superuser", "is_active"])

        db_user, db_user_created = DBUser.objects.update_or_create(
            login="test",
            defaults={"email": "test@gmail.com", "role": "Администратор", "is_active": True},
        )

        self.stdout.write(self.style.SUCCESS(f"Superuser admin {'created' if created else 'updated'}."))
        self.stdout.write(self.style.SUCCESS(f"DBUser test {'created' if db_user_created else 'updated'} with id={db_user.pk}."))
