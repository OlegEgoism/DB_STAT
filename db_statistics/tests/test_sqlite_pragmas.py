from unittest import mock

from django.db import connection
from django.test import TestCase

from db_statistics.apps import _sqlite_synchronous_mode


class SqlitePragmaTests(TestCase):
    def test_default_synchronous_mode_is_normal(self):
        with mock.patch.dict("os.environ", {}, clear=False):
            self.assertEqual(_sqlite_synchronous_mode().upper(), "NORMAL")

    def test_invalid_synchronous_value_falls_back_to_normal(self):
        with mock.patch.dict("os.environ", {"SQLITE_SYNCHRONOUS": "DROP TABLE x"}):
            self.assertEqual(_sqlite_synchronous_mode(), "NORMAL")

    def test_connection_uses_wal_and_chosen_pragmas(self):
        if connection.vendor != "sqlite":
            self.skipTest("тест только для SQLite")
        with connection.cursor() as cursor:
            # Тестовая база Django в SQLite работает в памяти, там журнал WAL невозможен.
            # Проверяем WAL только для файловой базы, остальные PRAGMA — всегда.
            if not connection.is_in_memory_db():
                cursor.execute("PRAGMA journal_mode")
                self.assertEqual(cursor.fetchone()[0].lower(), "wal")
            cursor.execute("PRAGMA temp_store")
            self.assertEqual(cursor.fetchone()[0], 2)  # 2 = MEMORY
