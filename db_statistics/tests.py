from django.contrib import admin
from django.test import SimpleTestCase

from db_statistics.admin import DBConnectionAdmin
from db_statistics.models import DBAudit, DBConnection
from db_statistics.view_helpers import MAINTENANCE_OPERATION_LABELS


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
