import json

import psycopg2
from django.test import SimpleTestCase, override_settings

from db_statistics.views.pool import _connection_kwargs, _db_error_response, _query_or_error


class _FakeDbError(psycopg2.Error):
    def __init__(self, sqlstate, text="внутренний текст БД: relation secret_table does not exist"):
        super().__init__(text)
        self._sqlstate = sqlstate

    @property
    def pgcode(self):
        return self._sqlstate


def _body(response):
    return json.loads(response.content)


def _raise(exc):
    def fn():
        raise exc

    return fn


@override_settings(DB_LOCK_TIMEOUT_MS=1234, DB_STATEMENT_TIMEOUT_MS=5678)
class ConnectionTimeoutOptionsTests(SimpleTestCase):
    def test_connection_options_carry_lock_and_statement_timeouts(self):
        kwargs = _connection_kwargs("db.internal", 5432, "app", "reader", "pw")

        self.assertIn("-c lock_timeout=1234", kwargs["options"])
        self.assertIn("-c statement_timeout=5678", kwargs["options"])


class TimeoutErrorResponseTests(SimpleTestCase):
    def test_lock_not_available_returns_503_with_locked_reason(self):
        data, response = _query_or_error("Не удалось получить размеры таблиц", _raise(_FakeDbError("55P03")))

        self.assertIsNone(data)
        self.assertEqual(response.status_code, 503)
        self.assertIn("заблокирован", _body(response)["message"])

    def test_query_canceled_returns_503_with_timeout_reason(self):
        _data, response = _query_or_error("Не удалось получить размеры таблиц", _raise(_FakeDbError("57014")))

        self.assertEqual(response.status_code, 503)
        self.assertIn("допустимое время", _body(response)["message"])

    def test_other_db_error_stays_400_and_hides_database_details(self):
        _data, response = _query_or_error("Не удалось получить размеры таблиц", _raise(_FakeDbError("42P01")))

        self.assertEqual(response.status_code, 400)
        self.assertNotIn("secret_table", _body(response)["message"])

    def test_response_helper_uses_action_as_prefix(self):
        response = _db_error_response("Не удалось X", _FakeDbError("55P03"))

        self.assertTrue(_body(response)["message"].startswith("Не удалось X. "))
