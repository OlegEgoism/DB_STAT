from io import StringIO

from django.core.management import call_command
from django.db import connection
from django.db.migrations.recorder import MigrationRecorder
from django.test import TransactionTestCase


class LegacyInstallMigrationTests(TransactionTestCase):
    """Установка, созданная до миграций: таблицы уже есть, а записи о 0001_initial в django_migrations нет."""

    def test_migrate_marks_existing_baseline_as_applied(self):
        recorder = MigrationRecorder(connection)
        recorder.migration_qs.filter(app="db_statistics").delete()

        # Без адаптации здесь падает InconsistentMigrationHistory: admin.0001 применена и зависит от 0001 db_statistics.
        call_command("migrate", fake_initial=True, interactive=False, stdout=StringIO())

        self.assertTrue(recorder.migration_qs.filter(app="db_statistics", name="0001_initial").exists())
