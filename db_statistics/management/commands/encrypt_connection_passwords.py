from django.core.management.base import BaseCommand

from db_statistics.models import ENCRYPTED_PASSWORD_PREFIX, DBConnection


class Command(BaseCommand):
    """Шифрует пароли подключений, сохранённые в БД в открытом виде.

    Раньше это делалось незаметно при первом чтении пароля (DBConnection.get_password).
    Эта команда переносит разовую миграцию старых записей в явное, управляемое действие.
    Model.save() уже шифрует self.password, поэтому команде достаточно найти
    записи с ещё не зашифрованным паролем и пересохранить их.
    """

    help = "Шифрует незашифрованные пароли подключений (наследие до включения шифрования)"

    def handle(self, *args, **options):
        migrated = 0
        for connection in DBConnection.objects.all():
            if connection.password and not connection.password.startswith(ENCRYPTED_PASSWORD_PREFIX):
                connection.save(update_fields=["password", "updated"])
                migrated += 1
        self.stdout.write(self.style.SUCCESS(f"Зашифровано подключений: {migrated}"))
