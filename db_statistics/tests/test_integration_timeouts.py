import json
import threading
import time

from django.test import override_settings

from db_statistics.tests.pg_base import SCHEMA, PostgresTestCase
from db_statistics.views.pool import _fetch_db_row, _fetch_db_rows, _open_database_connection, _query_or_error


class LockedTableIntegrationTests(PostgresTestCase):
    def test_request_on_locked_table_fails_fast_instead_of_hanging(self):
        with override_settings(DB_LOCK_TIMEOUT_MS=500):
            holder = self._target_connection()
            holder.autocommit = False
            # Страховка: если таймаут сломается, блокировка всё равно снимется через 8 с,
            # и тест упадёт с понятным провалом, а не повиснет навсегда.
            safety_release = threading.Timer(8, holder.rollback)
            safety_release.start()
            try:
                with holder.cursor() as cursor:
                    cursor.execute(f"LOCK TABLE {SCHEMA}.orders IN ACCESS EXCLUSIVE MODE")
                started = time.monotonic()
                response = self.post_json("/tables/sizes/", {"search": "orders"})
                elapsed = time.monotonic() - started
            finally:
                safety_release.cancel()
                holder.rollback()
                holder.close()

        self.assertEqual(response.status_code, 503)
        self.assertIn("заблокирован", response.json()["message"])
        self.assertLess(elapsed, 5)


class StatementTimeoutIntegrationTests(PostgresTestCase):
    def test_slow_query_is_cancelled_by_statement_timeout(self):
        with override_settings(DB_STATEMENT_TIMEOUT_MS=300):
            _data, response = _query_or_error("Тест", lambda: _fetch_db_rows(self.connection, "SELECT pg_sleep(3)"))

        self.assertEqual(response.status_code, 503)
        self.assertIn("допустимое время", json.loads(response.content)["message"])


class BackgroundTimeoutIntegrationTests(PostgresTestCase):
    @override_settings(DB_LOCK_TIMEOUT_MS=3000, DB_STATEMENT_TIMEOUT_MS=15000, DB_BACKGROUND_LOCK_TIMEOUT_MS=30000, DB_BACKGROUND_STATEMENT_TIMEOUT_MS=600000)
    def test_background_connection_gets_longer_timeouts_and_pool_gets_defaults_back(self):
        with _open_database_connection(self.connection, background=True) as connection, connection.cursor() as cursor:
            cursor.execute("SHOW statement_timeout")
            inside_statement = cursor.fetchone()[0]
            cursor.execute("SHOW lock_timeout")
            inside_lock = cursor.fetchone()[0]

        self.assertEqual(inside_statement, "10min")
        self.assertEqual(inside_lock, "30s")
        self.assertEqual(_fetch_db_row(self.connection, "SHOW statement_timeout")[0], "15s")
        self.assertEqual(_fetch_db_row(self.connection, "SHOW lock_timeout")[0], "3s")
