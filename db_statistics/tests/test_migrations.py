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


class LegacyColumnReconciliationTests(TransactionTestCase):
    """Установка, созданная раньше колонки db_type, получает её при адаптации и не теряет данные."""

    def test_missing_column_is_added_and_existing_rows_are_kept(self):
        from db_statistics.management.commands.migrate import add_missing_columns
        from db_statistics.models import DBConnection

        connection_row = DBConnection.objects.create(name="legacy", host="db.internal", port=5432, database="app", username="reader", password="pw")
        with connection.schema_editor() as editor:
            editor.remove_field(DBConnection, DBConnection._meta.get_field("db_type"))
        with connection.cursor() as cursor:
            columns = {c.name for c in connection.introspection.get_table_description(cursor, DBConnection._meta.db_table)}
        self.assertNotIn("db_type", columns)

        added = add_missing_columns(connection)

        self.assertEqual(added, ["db_connection.db_type"])
        connection_row.refresh_from_db()
        self.assertEqual(connection_row.name, "legacy")
        self.assertEqual(connection_row.db_type, "PostgreSQL")

    def test_nothing_is_added_when_schema_is_complete(self):
        from db_statistics.management.commands.migrate import add_missing_columns

        self.assertEqual(add_missing_columns(connection), [])
