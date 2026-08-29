from django.test import SimpleTestCase

from db_statistics.models import DBConnection


class DBConnectionTypeTests(SimpleTestCase):
    def test_greengage_is_available_database_type(self):
        self.assertIn(("Greengage", "Greengage"), DBConnection.DATABASE_TYPES)

    def test_distributed_database_compatibility(self):
        for db_type in ("Greenplum", "Greengage"):
            with self.subTest(db_type=db_type):
                self.assertTrue(DBConnection(db_type=db_type).is_greenplum_compatible)

        self.assertFalse(DBConnection(db_type="PostgreSQL").is_greenplum_compatible)
