"""Базовый класс интеграционных тестов против настоящего PostgreSQL.

Тесты пропускаются, если не задан PG_TEST_HOST. В CI этот сервис поднимается
отдельно (см. .github/workflows/ci.yml), поэтому там пропусков быть не должно.

Переменные окружения:
  PG_TEST_HOST, PG_TEST_PORT (по умолчанию 5432), PG_TEST_USER (postgres),
  PG_TEST_PASSWORD, PG_TEST_DATABASE (postgres).
"""

import json
import os
import unittest

import psycopg2
from django.test import TestCase

from db_statistics.models import DBConnection, DBUser
from db_statistics.views.pool import _close_connection_pools_for

PASSWORD = "integration-test-password"
SCHEMA = "dbstat_it"
ROLE_GROUP = "dbstat_it_group"


def _target_settings():
    host = os.environ.get("PG_TEST_HOST")
    if not host:
        return None
    return {"host": host, "port": int(os.environ.get("PG_TEST_PORT", "5432")), "user": os.environ.get("PG_TEST_USER", "postgres"), "password": os.environ.get("PG_TEST_PASSWORD", ""), "database": os.environ.get("PG_TEST_DATABASE", "postgres")}


class PostgresTestCase(TestCase):
    """Создаёт в целевой БД схему с тестовыми таблицами и входит в приложение."""

    target = None

    @classmethod
    def setUpClass(cls):
        cls.target = _target_settings()
        if cls.target is None:
            raise unittest.SkipTest("PG_TEST_HOST не задан: интеграционные тесты пропущены")
        cls._seed_target()
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        if cls.target is not None:
            with cls._target_connection() as connection, connection.cursor() as cursor:
                cursor.execute(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE")
                cursor.execute(f"DROP ROLE IF EXISTS {ROLE_GROUP}")

    @classmethod
    def _target_connection(cls):
        connection = psycopg2.connect(host=cls.target["host"], port=cls.target["port"], user=cls.target["user"], password=cls.target["password"], dbname=cls.target["database"], connect_timeout=10)
        connection.autocommit = True
        return connection

    @classmethod
    def _seed_target(cls):
        with cls._target_connection() as connection, connection.cursor() as cursor:
            cursor.execute(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE")
            cursor.execute(f"CREATE SCHEMA {SCHEMA}")
            cursor.execute(f"CREATE TABLE {SCHEMA}.orders (id int, note text)")
            cursor.execute(f"INSERT INTO {SCHEMA}.orders SELECT g, 'order ' || g FROM generate_series(1, 25) g")
            # Случайные данные не сжимаются: значения больше ~2 КБ уходят в TOAST-таблицу.
            # Повторяющаяся строка сжималась бы до размера страницы и TOAST не создавался бы.
            cursor.execute(f"CREATE TABLE {SCHEMA}.documents (id int, body text)")
            cursor.execute(f"INSERT INTO {SCHEMA}.documents SELECT g, (SELECT string_agg(md5(random()::text), '') FROM generate_series(1, 300)) FROM generate_series(1, 20) g")
            # Без TEXT/JSONB и без TOAST-таблицы с данными: в TOAST-списке её быть не должно.
            cursor.execute(f"CREATE TABLE {SCHEMA}.small (id int)")
            cursor.execute(f"INSERT INTO {SCHEMA}.small VALUES (1)")
            cursor.execute(f"CREATE VIEW {SCHEMA}.v_orders AS SELECT id, note FROM {SCHEMA}.orders")
            cursor.execute(f"CREATE MATERIALIZED VIEW {SCHEMA}.mv_orders AS SELECT id FROM {SCHEMA}.orders")
            cursor.execute(f"CREATE FUNCTION {SCHEMA}.f_orders_count() RETURNS bigint LANGUAGE sql AS 'SELECT count(*) FROM {SCHEMA}.orders'")
            cursor.execute(f"ANALYZE {SCHEMA}.orders, {SCHEMA}.documents, {SCHEMA}.small")
            # Роли кластерные: создаём и удаляем в тестовом классе, чтобы не оставлять следов.
            cursor.execute(f"DROP ROLE IF EXISTS {ROLE_GROUP}")
            cursor.execute(f"CREATE ROLE {ROLE_GROUP} NOLOGIN")

    def setUp(self):
        self.user = DBUser.objects.create_user(login="it_analyst", email="it_analyst@example.com", password=PASSWORD)
        self.connection = self._make_connection(name="integration", password=self.target["password"])
        self.user.connections.add(self.connection)
        self._login(self.user.login)

    def tearDown(self):
        _close_connection_pools_for(self.connection.pk)
        super().tearDown()

    def _make_connection(self, name, password):
        return DBConnection.objects.create(name=name, host=self.target["host"], port=self.target["port"], database=self.target["database"], username=self.target["user"], password=password, db_type=DBConnection.POSTGRESQL)

    def _login(self, login):
        response = self.client.post("/login/", {"identifier": login, "password": PASSWORD, "session_duration": "1"})
        self.assertEqual(response.status_code, 302, "вход в приложение в интеграционном тесте не выполнен")

    def post_json(self, path, payload=None, connection=None):
        body = {"id": (connection or self.connection).pk, **(payload or {})}
        return self.client.post(path, data=json.dumps(body), content_type="application/json")
