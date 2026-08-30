from datetime import timedelta
from unittest.mock import patch

from django.conf import settings
from django.contrib import admin
from django.core.management import call_command
from django.test import RequestFactory, SimpleTestCase, TestCase
from django.utils import timezone

from db_statistics.admin import DBConnectionAdmin
from db_statistics.models import DBAudit, DBConnection, DBFavorite, DBUser, DBUserSidebarSettings, MaintenanceJob
from db_statistics.view_helpers import MAINTENANCE_OPERATION_LABELS, _like_search_pattern, _multi_column_search_filter, _serialize_maintenance_job
from db_statistics.views_data import FUNCTION_SEARCH_COLUMNS, SCHEMA_SEARCH_COLUMNS, TABLE_SEARCH_COLUMNS, TEMP_TABLE_SEARCH_COLUMNS, VIEW_SEARCH_COLUMNS
from db_statistics.views_performance import blocking_locks, idle_transactions


class MaintenanceQueueTests(TestCase):
    def setUp(self):
        self.user = DBUser.objects.create(login="queue-admin", email="queue@example.com", role="Администратор")
        self.connection = DBConnection.objects.create(name="queue-db", host="db", database="postgres", username="monitor", password="secret")

    def test_recover_command_returns_interrupted_job_to_queue(self):
        job = MaintenanceJob.objects.create(
            user=self.user,
            connection=self.connection,
            operation="analyze",
            schema_name="public",
            table_name="events",
            status="running",
        )

        call_command("recover_maintenance_jobs")

        job.refresh_from_db()
        self.assertEqual(job.status, "queued")
        self.assertIn("восстановлена", job.message)

    def test_completed_jobs_keep_result_history(self):
        started = timezone.now()
        finished = started + timedelta(seconds=3)
        job = MaintenanceJob.objects.create(
            user=self.user,
            connection=self.connection,
            operation="vacuum",
            schema_name="public",
            table_name="events",
            status="completed",
            details=["done"],
            statistics={"live_rows": 10, "dead_rows": 0},
            started=started,
            finished=finished,
        )

        self.assertEqual(MaintenanceJob.objects.get(pk=job.pk).statistics["live_rows"], 10)
        serialized = _serialize_maintenance_job(job)
        self.assertEqual(serialized["username"], self.user.login)
        self.assertEqual(serialized["started"], started.isoformat())
        self.assertEqual(serialized["finished"], finished.isoformat())


class ModelHelpTextTests(SimpleTestCase):
    def test_all_declared_model_fields_have_help_text(self):
        models = (DBUser, DBUserSidebarSettings, DBFavorite, DBConnection, DBAudit, MaintenanceJob)
        for model in models:
            for field in (*model._meta.fields, *model._meta.many_to_many):
                if field.auto_created:
                    continue
                with self.subTest(model=model.__name__, field=field.name):
                    self.assertTrue(field.help_text)

    def test_maintenance_job_has_descriptive_metadata(self):
        self.assertEqual(MaintenanceJob._meta.db_table, "db_maintenance_job")
        self.assertEqual(
            MaintenanceJob._meta.verbose_name,
            "Фоновая операция обслуживания",
        )
        self.assertEqual(
            MaintenanceJob._meta.verbose_name_plural,
            "Фоновые операции обслуживания",
        )


class ApplicationDatabaseTests(SimpleTestCase):
    def test_application_database_uses_sqlite(self):
        self.assertEqual(
            settings.DATABASES["default"]["ENGINE"],
            "django.db.backends.sqlite3",
        )


class SearchTests(SimpleTestCase):
    def test_search_columns_match_field_descriptions(self):
        self.assertEqual(SCHEMA_SEARCH_COLUMNS, ("namespace.nspname",))
        self.assertEqual(
            TABLE_SEARCH_COLUMNS,
            (
                "namespace.nspname",
                "table_class.relname",
                "(namespace.nspname || '.' || table_class.relname)",
            ),
        )
        self.assertEqual(
            VIEW_SEARCH_COLUMNS,
            (
                "namespace.nspname",
                "view_class.relname",
                "(namespace.nspname || '.' || view_class.relname)",
            ),
        )
        self.assertEqual(TEMP_TABLE_SEARCH_COLUMNS, TABLE_SEARCH_COLUMNS)
        self.assertEqual(
            FUNCTION_SEARCH_COLUMNS,
            (
                "namespace.nspname",
                "procedure.proname",
                "pg_catalog.pg_get_function_result(procedure.oid)",
                "pg_catalog.pg_get_function_arguments(procedure.oid)",
            ),
        )

    def test_like_search_escapes_wildcards_without_losing_substring_search(self):
        self.assertEqual(_like_search_pattern("ops_100%!"), "%ops!_100!%!!%")

    def test_multi_column_search_uses_every_described_data_column(self):
        where_sql, params = _multi_column_search_filter(
            "Sales_2026", ("schema_name", "table_name")
        )
        self.assertEqual(
            where_sql,
            "AND (schema_name ILIKE %s ESCAPE '!' OR table_name ILIKE %s ESCAPE '!')",
        )
        self.assertEqual(params, ["%Sales!_2026%", "%Sales!_2026%"])

    @patch("db_statistics.views_performance._fetch_db_rows", return_value=[])
    @patch("db_statistics.views_performance._require_payload_connection")
    @patch("db_statistics.views_performance._read_json_body")
    def test_lock_user_fields_search_by_partial_value(
        self, read_body, require_connection, fetch_rows
    ):
        read_body.return_value = {
            "blocked_username": "ops_",
            "blocker_username": "Admin%",
        }
        require_connection.return_value = (object(), None)

        response = blocking_locks(RequestFactory().post("/locks"))

        self.assertEqual(response.status_code, 200)
        query, params = fetch_rows.call_args.args[1:]
        self.assertIn("blocked.usename ILIKE %s ESCAPE '!'", query)
        self.assertIn("blocker.usename ILIKE %s ESCAPE '!'", query)
        self.assertEqual(params, ["ops_", "%ops!_%", "Admin%", "%Admin!%%"])

    @patch("db_statistics.views_performance._fetch_db_rows", return_value=[])
    @patch("db_statistics.views_performance._require_payload_connection")
    @patch("db_statistics.views_performance._read_json_body")
    def test_idle_transaction_user_field_searches_by_partial_value(
        self, read_body, require_connection, fetch_rows
    ):
        read_body.return_value = {"username": "report_"}
        require_connection.return_value = (object(), None)

        response = idle_transactions(RequestFactory().post("/transactions"))

        self.assertEqual(response.status_code, 200)
        query, params = fetch_rows.call_args.args[1:]
        self.assertIn("usename ILIKE %s ESCAPE '!'", query)
        self.assertEqual(params, ["report_", "%report!_%"])


class DBConnectionTypeTests(SimpleTestCase):
    def test_greengage_is_available_database_type(self):
        self.assertIn(("Greengage", "Greengage"), DBConnection.DATABASE_TYPES)

    def test_distributed_database_compatibility(self):
        for db_type in ("Greenplum", "Greengage"):
            with self.subTest(db_type=db_type):
                self.assertTrue(DBConnection(db_type=db_type).is_greenplum_compatible)

        self.assertFalse(DBConnection(db_type="PostgreSQL").is_greenplum_compatible)


class MaintenanceOperationTests(SimpleTestCase):
    def test_background_operations_have_labels_and_audit_types(self):
        expected_operations = {"vacuum", "vacuum_full", "analyze", "explain_analyze"}
        self.assertEqual(set(MAINTENANCE_OPERATION_LABELS), expected_operations)
        self.assertTrue(expected_operations.issubset(dict(DBAudit.ACTION_TYPES)))


class DBConnectionAdminTests(SimpleTestCase):
    def test_assigned_user_logins_are_visible_and_searchable(self):
        model_admin = admin.site._registry[DBConnection]
        self.assertIsInstance(model_admin, DBConnectionAdmin)
        self.assertIn("users_logins", model_admin.list_display)
        self.assertIn("users_logins", model_admin.readonly_fields)
        self.assertIn("dbuser__login", model_admin.search_fields)
