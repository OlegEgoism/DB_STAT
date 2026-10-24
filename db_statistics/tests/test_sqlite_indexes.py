import json

from django.core.management import call_command
from django.db import connection
from django.test import TestCase, TransactionTestCase
from django.test.utils import CaptureQueriesContext

from db_statistics.models import DBConnection, DBUser, ReportJob
from db_statistics.tests.pg_base import PASSWORD


def _index_names(table):
    with connection.cursor() as cursor:
        return {name for name, info in connection.introspection.get_constraints(cursor, table).items() if info["index"]}


class ReportListDoesNotLoadPdfTests(TestCase):
    def setUp(self):
        self.user = DBUser.objects.create_user(login="pdf_list", email="pdf_list@example.com", password=PASSWORD)
        self.connection = DBConnection.objects.create(name="pdf", host="db", port=5432, database="app", username="r", password="p")
        self.user.connections.add(self.connection)
        ReportJob.objects.create(user=self.user, connection=self.connection, status="completed", content=b"%PDF-" + b"x" * 200_000, filename="a.pdf")
        self.client.post("/login/", {"identifier": "pdf_list", "password": PASSWORD, "session_duration": "1"})

    def test_report_list_query_does_not_read_pdf_column(self):
        with CaptureQueriesContext(connection) as ctx:
            response = self.client.get("/reports/database.pdf")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(json.loads(response.content)["reports"]), 1)
        report_selects = [q["sql"] for q in ctx.captured_queries if "db_report_job" in q["sql"] and q["sql"].lstrip().upper().startswith("SELECT")]
        self.assertTrue(report_selects)
        self.assertFalse(any('"db_report_job"."content"' in sql for sql in report_selects))


class EnsureIndexesTests(TransactionTestCase):
    # Изменение схемы SQLite невозможно внутри транзакции TestCase; в самой команде транзакции нет.
    def test_missing_index_is_recreated(self):
        with connection.cursor() as cursor:
            cursor.execute("DROP INDEX IF EXISTS db_audit_username_created")
        self.assertNotIn("db_audit_username_created", _index_names("db_audit"))

        call_command("ensure_indexes", stdout=open("/dev/null", "w"))

        self.assertIn("db_audit_username_created", _index_names("db_audit"))

    def test_second_run_is_a_no_op(self):
        call_command("ensure_indexes", stdout=open("/dev/null", "w"))
        before = _index_names("db_maintenance_job")

        call_command("ensure_indexes", stdout=open("/dev/null", "w"))

        self.assertEqual(before, _index_names("db_maintenance_job"))

    def test_declared_indexes_exist_after_sync(self):
        for table, name in [("db_audit", "db_audit_action_created"), ("db_maintenance_job", "db_maint_user_created"), ("db_report_job", "db_report_user_created")]:
            self.assertIn(name, _index_names(table))
