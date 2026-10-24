import datetime

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from db_statistics.models import DBAudit


class Command(BaseCommand):
    help = "Удаляет записи журнала аудита старше указанного срока. Без --yes только показывает, сколько записей будет удалено"

    def add_arguments(self, parser):
        parser.add_argument("--older-than-days", type=int, required=True, help="Удалять записи старше стольких дней (минимум 30)")
        parser.add_argument("--yes", action="store_true", help="Действительно удалить. Без этого флага команда ничего не меняет")

    def handle(self, *args, **options):
        days = options["older_than_days"]
        if days < 30:
            raise CommandError("Срок хранения — не меньше 30 дней: короткий срок стирает свежие следы действий")
        cutoff = timezone.now() - datetime.timedelta(days=days)
        queryset = DBAudit.objects.filter(created__lt=cutoff)
        total = queryset.count()
        if not options["yes"]:
            self.stdout.write(f"Будет удалено записей старше {days} дн. (до {cutoff:%Y-%m-%d %H:%M}): {total}. Запустите с --yes, чтобы удалить.")
            return
        with transaction.atomic():
            deleted, _ = queryset.delete()
        self.stdout.write(self.style.SUCCESS(f"Удалено записей аудита старше {days} дн.: {deleted}"))
