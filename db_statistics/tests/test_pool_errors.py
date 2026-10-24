import json
from unittest import mock

import psycopg2
from django.test import SimpleTestCase
from psycopg2.pool import PoolError

from db_statistics.views.pool import POOL_EXHAUSTED_MESSAGE, _db_error_response, _fetch_db_rows, _query_or_error


def _body(response):
    return json.loads(response.content)


class _ExhaustedPool:
    """Имитирует пул, в котором все соединения заняты: getconn() бросает PoolError."""

    def getconn(self, key=None):
        raise PoolError("connection pool exhausted")


class PoolExhaustedResponseTests(SimpleTestCase):
    def test_pool_error_maps_to_503_with_pool_message(self):
        response = _db_error_response("Не удалось получить размеры таблиц", PoolError("connection pool exhausted"))

        self.assertEqual(response.status_code, 503)
        self.assertEqual(_body(response)["message"], f"Не удалось получить размеры таблиц. {POOL_EXHAUSTED_MESSAGE}")
        self.assertEqual(POOL_EXHAUSTED_MESSAGE, "Превышен лимит соединений с целевой БД: попробуйте позже")

    def test_pool_error_is_handled_before_generic_db_error(self):
        # PoolError — подкласс psycopg2.Error; без явной проверки он стал бы 400.
        self.assertTrue(issubclass(PoolError, psycopg2.Error))

        _data, response = _query_or_error("Не удалось получить активные запросы", mock.Mock(side_effect=PoolError("connection pool exhausted")))

        self.assertEqual(response.status_code, 503)
        self.assertIn("Превышен лимит соединений", _body(response)["message"])

    def test_exhausted_pool_surfaces_as_503_through_fetch_path(self):
        # Полный путь: _fetch_db_rows берёт соединение из пула, пул отказывает — ответ 503, а не 400.
        with mock.patch("db_statistics.views.pool._get_connection_pool", return_value=_ExhaustedPool()):
            _rows, response = _query_or_error("Не удалось получить сессии", lambda: _fetch_db_rows(mock.Mock(), "SELECT 1"))

        self.assertEqual(response.status_code, 503)
        self.assertIn(POOL_EXHAUSTED_MESSAGE, _body(response)["message"])
