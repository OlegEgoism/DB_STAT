from io import StringIO

from django.core.management import call_command
from django.db import connection
from django.db.migrations.recorder import MigrationRecorder
from django.test import TestCase, TransactionTestCase


class ModelsMatchMigrationsTests(TestCase):
    """Изменение модели без миграции ломает тесты: иначе новая схема не дойдёт до уже развёрнутых установок."""

    def test_no_pending_migrations_for_db_statistics(self):
        out = StringIO()
        has_changes = False
        try:
            call_command("makemigrations", "db_statistics", check=True, dry_run=True, verbosity=1, stdout=out, stderr=out)
        except SystemExit:
            # makemigrations --check завершается с кодом 1, только если модели изменены без миграции.
            has_changes = True
        if has_changes:
            self.fail(f"Модели db_statistics изменены без миграции. Выполните `make migrations` и закоммитьте файл миграции.\n{out.getvalue()}")
        self.assertIn("No changes detected", out.getvalue())


class LegacyInstallMigrationTests(TransactionTestCase):
    """Установка, созданная до миграций: таблицы уже есть, а записи о 0001_initial в django_migrations нет."""

    def test_migrate_marks_existing_baseline_as_applied(self):
        recorder = MigrationRecorder(connection)
        recorder.migration_qs.filter(app="db_statistics").delete()

        # Без адаптации здесь падает InconsistentMigrationHistory: admin.0001 применена и зависит от 0001 db_statistics.
        call_command("migrate", fake_initial=True, interactive=False, stdout=StringIO())

        self.assertTrue(recorder.migration_qs.filter(app="db_statistics", name="0001_initial").exists())
