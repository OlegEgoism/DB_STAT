import json
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import RequestFactory, SimpleTestCase

from db_statistics.views import MAINTENANCE_JOBS, SESSION_EXPIRES_AT_KEY, SIDEBAR_SECTION_IDS, SIDEBAR_TAB_IDS, _normalize_sidebar_sections, _normalize_sidebar_tabs, _session_duration_seconds, _session_has_expired, _sidebar_settings_values, active_queries, active_sessions, maintenance_vacuum, terminate_active_query, terminate_active_session


class SidebarTabNormalizationTests(SimpleTestCase):
    def test_preserves_custom_order_and_removes_duplicates(self):
        tabs = ["tables", "databases", "tables", "audit"]

        self.assertEqual(_normalize_sidebar_tabs(tabs), ["tables", "databases", "audit", "settings"])

    def test_ignores_unknown_tabs(self):
        self.assertEqual(_normalize_sidebar_tabs(["tables", "unknown", "users"]), ["tables", "users", "settings"])

    def test_keeps_settings_visible_without_changing_its_order(self):
        self.assertEqual(_normalize_sidebar_tabs(["settings", "audit", "favorites"]), ["settings", "audit", "favorites"])

    def test_uses_default_order_when_selection_is_empty(self):
        self.assertEqual(_normalize_sidebar_tabs([]), SIDEBAR_TAB_IDS)


class SidebarSectionNormalizationTests(SimpleTestCase):
    def test_preserves_custom_order_and_adds_missing_sections(self):
        self.assertEqual(
            _normalize_sidebar_sections(["additional", "data", "additional", "unknown"]),
            ["additional", "data", "infrastructure", "performance", "administration"],
        )

    def test_uses_default_order_for_invalid_value(self):
        self.assertEqual(_normalize_sidebar_sections(None), SIDEBAR_SECTION_IDS)

    def test_reads_tabs_and_section_order_from_combined_settings(self):
        settings = SimpleNamespace(visible_tabs={
            "visible_tabs": ["tables", "audit"],
            "section_order": ["additional", "data"],
        })

        tabs, sections = _sidebar_settings_values(settings)

        self.assertEqual(tabs, ["tables", "audit", "settings"])
        self.assertEqual(sections, ["additional", "data", "infrastructure", "performance", "administration"])


class SessionDurationTests(SimpleTestCase):
    def test_accepts_duration_from_ten_minutes_to_twenty_four_hours(self):
        self.assertEqual(_session_duration_seconds("0.1667"), 600)
        self.assertEqual(_session_duration_seconds("0.5"), 1800)
        self.assertEqual(_session_duration_seconds("24"), 86400)

    def test_rejects_duration_outside_limits(self):
        self.assertIsNone(_session_duration_seconds("0.16"))
        self.assertIsNone(_session_duration_seconds("24.01"))

    def test_rejects_non_numeric_duration(self):
        self.assertIsNone(_session_duration_seconds("invalid"))


class SessionExpirationTests(SimpleTestCase):
    def test_detects_expired_session(self):
        self.assertTrue(_session_has_expired({SESSION_EXPIRES_AT_KEY: 100}, now_timestamp=100))
        self.assertTrue(_session_has_expired({SESSION_EXPIRES_AT_KEY: 99}, now_timestamp=100))

    def test_keeps_active_and_legacy_sessions(self):
        self.assertFalse(_session_has_expired({SESSION_EXPIRES_AT_KEY: 101}, now_timestamp=100))
        self.assertFalse(_session_has_expired({}, now_timestamp=100))

    def test_rejects_invalid_expiration_timestamp(self):
        self.assertTrue(_session_has_expired({SESSION_EXPIRES_AT_KEY: "invalid"}, now_timestamp=100))


class MaintenanceVacuumTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = SimpleNamespace(pk=11)
        self.connection = SimpleNamespace(pk=7)
        MAINTENANCE_JOBS.clear()

    @patch("db_statistics.views.MAINTENANCE_JOB_EXECUTOR.submit")
    @patch("db_statistics.views._require_payload_connection")
    @patch("db_statistics.views._current_db_user")
    def test_starts_vacuum_full_in_background(self, current_user, require_connection, submit):
        current_user.return_value = self.user
        require_connection.return_value = (self.connection, None)
        request = self.factory.post(
            "/maintenance/vacuum/",
            data=json.dumps({"id": 7, "schema_name": "public", "table_name": "orders", "operation": "vacuum_full"}),
            content_type="application/json",
        )

        response = maintenance_vacuum(request)
        payload = json.loads(response.content)

        self.assertEqual(response.status_code, 202)
        self.assertEqual(payload["job"]["status"], "running")
        self.assertEqual(payload["job"]["operation"], "vacuum_full")
        submit.assert_called_once()

    @patch("db_statistics.views._current_db_user")
    def test_returns_owned_job_status(self, current_user):
        current_user.return_value = self.user
        MAINTENANCE_JOBS["job-1"] = {"id": "job-1", "user_id": 11, "status": "completed", "operation": "vacuum"}
        request = self.factory.post(
            "/maintenance/vacuum/",
            data=json.dumps({"job_id": "job-1"}),
            content_type="application/json",
        )

        response = maintenance_vacuum(request)
        payload = json.loads(response.content)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["job"]["status"], "completed")
        self.assertNotIn("user_id", payload["job"])


class ActiveSessionsFilterTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.connection = Mock(name="saved_connection")

    @patch("db_statistics.views._fetch_db_rows", return_value=[])
    @patch("db_statistics.views._require_payload_connection")
    def test_filters_username_by_case_insensitive_substring(self, require_connection, fetch_rows):
        require_connection.return_value = (self.connection, None)
        request = self.factory.post(
            "/sessions/active/",
            data=json.dumps({"id": 7, "username": "Anal", "state": ""}),
            content_type="application/json",
        )

        response = active_sessions(request)

        self.assertEqual(response.status_code, 200)
        _connection, query, params = fetch_rows.call_args.args
        self.assertIn("usename ILIKE %s ESCAPE '!'", query)
        self.assertEqual(params, ["Anal", "%Anal%", "", ""])

    @patch("db_statistics.views._fetch_db_rows", return_value=[])
    @patch("db_statistics.views._require_payload_connection")
    def test_escapes_like_wildcards_in_username(self, require_connection, fetch_rows):
        require_connection.return_value = (self.connection, None)
        request = self.factory.post(
            "/sessions/active/",
            data=json.dumps({"id": 7, "username": "user_%", "state": "active"}),
            content_type="application/json",
        )

        response = active_sessions(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(fetch_rows.call_args.args[2], ["user_%", "%user!_!%%", "active", "active"])


class ActiveQueriesFilterTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.connection = Mock(name="saved_connection")

    @patch("db_statistics.views._fetch_db_rows", return_value=[])
    @patch("db_statistics.views._require_payload_connection")
    def test_filters_username_by_case_insensitive_substring(self, require_connection, fetch_rows):
        require_connection.return_value = (self.connection, None)
        request = self.factory.post(
            "/queries/active/",
            data=json.dumps({"id": 7, "username": "Anal"}),
            content_type="application/json",
        )

        response = active_queries(request)

        self.assertEqual(response.status_code, 200)
        _connection, query, params = fetch_rows.call_args.args
        self.assertIn("activity.usename ILIKE %s ESCAPE '!'", query)
        self.assertEqual(params, ["Anal", "%Anal%"])

    @patch("db_statistics.views._fetch_db_rows", return_value=[])
    @patch("db_statistics.views._require_payload_connection")
    def test_escapes_like_wildcards_in_username(self, require_connection, fetch_rows):
        require_connection.return_value = (self.connection, None)
        request = self.factory.post(
            "/queries/active/",
            data=json.dumps({"id": 7, "username": "user_%"}),
            content_type="application/json",
        )

        response = active_queries(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(fetch_rows.call_args.args[2], ["user_%", "%user!_!%%"])


class TerminateActiveQueryTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.connection = Mock(name="saved_connection")
        self.connection.name = "Основная БД"
        self.connection.db_type = "PostgreSQL"
        self.connection.host = "db.example.test"
        self.connection.port = 5432
        self.connection.database = "analytics"
        self.connection.username = "monitor"

    def request(self, pid):
        request = self.factory.post(
            "/queries/terminate/",
            data=json.dumps({"id": 7, "pid": pid}),
            content_type="application/json",
        )
        request.session = {}
        return request

    @patch("db_statistics.views._write_audit")
    @patch("db_statistics.views._fetch_db_row", return_value=(True, 1234, "analyst", "analytics", "psql", "10.0.0.5", 55123, "active", "client backend", "2026-08-11 10:00:00", "2026-08-11 10:04:00", "2026-08-11 10:05:00", "2026-08-11 10:05:00", "Lock", "relation", "0:10:00", "0:05:00", "SELECT * FROM sales"))
    @patch("db_statistics.views._require_payload_connection")
    def test_terminates_active_backend_by_pid(self, require_connection, fetch_row, write_audit):
        require_connection.return_value = (self.connection, None)

        response = terminate_active_query(self.request(1234))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.content), {"ok": True, "message": "Запрос с PID 1234 завершён", "pid": 1234})
        connection, query, params = fetch_row.call_args.args
        self.assertIs(connection, self.connection)
        self.assertIn("pg_terminate_backend", query)
        self.assertEqual(params, [1234])
        action_type, info = write_audit.call_args.args
        self.assertEqual(action_type, "query_terminate")
        self.assertIn("PID: 1234", info)
        self.assertIn("Пользователь сессии: analyst", info)
        self.assertIn("Ожидание: Lock / relation", info)
        self.assertIn("Длительность запроса: 0:05:00", info)
        self.assertIn("SQL: SELECT * FROM sales", info)

    @patch("db_statistics.views._require_payload_connection")
    def test_rejects_invalid_pid(self, require_connection):
        require_connection.return_value = (self.connection, None)

        response = terminate_active_query(self.request("not-a-pid"))

        self.assertEqual(response.status_code, 400)
        self.assertIn("некорректный PID", json.loads(response.content)["message"])

    @patch("db_statistics.views._fetch_db_row", return_value=None)
    @patch("db_statistics.views._require_payload_connection")
    def test_returns_not_found_when_query_is_no_longer_active(self, require_connection, _fetch_row):
        require_connection.return_value = (self.connection, None)

        response = terminate_active_query(self.request(1234))

        self.assertEqual(response.status_code, 404)


class TerminateActiveSessionTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.connection = Mock(name="saved_connection")
        self.connection.name = "Основная БД"
        self.connection.db_type = "PostgreSQL"
        self.connection.host = "db.example.test"
        self.connection.port = 5432
        self.connection.database = "analytics"
        self.connection.username = "monitor"

    def request(self, pid):
        request = self.factory.post(
            "/sessions/terminate/",
            data=json.dumps({"id": 7, "pid": pid}),
            content_type="application/json",
        )
        request.session = {}
        return request

    @patch("db_statistics.views._write_audit")
    @patch("db_statistics.views._fetch_db_row", return_value=(True, 4321, "reporter", "analytics", "DBeaver", "10.0.0.8", 60200, "idle", "client backend", "2026-08-11 09:00:00", None, "2026-08-11 09:30:00", "2026-08-11 09:30:01", "Client", "ClientRead", "1:30:00", "1:00:00", "SELECT 1"))
    @patch("db_statistics.views._require_payload_connection")
    def test_terminates_session_by_pid(self, require_connection, fetch_row, write_audit):
        require_connection.return_value = (self.connection, None)

        response = terminate_active_session(self.request(4321))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.content), {"ok": True, "message": "Сессия с PID 4321 завершена", "pid": 4321})
        connection, query, params = fetch_row.call_args.args
        self.assertIs(connection, self.connection)
        self.assertIn("pg_terminate_backend", query)
        self.assertNotIn("state = 'active'", query)
        self.assertEqual(params, [4321])
        action_type, info = write_audit.call_args.args
        self.assertEqual(action_type, "session_terminate")
        self.assertIn("PID: 4321", info)
        self.assertIn("Приложение: DBeaver", info)
        self.assertIn("Клиент: 10.0.0.8:60200", info)

    @patch("db_statistics.views._require_payload_connection")
    def test_rejects_invalid_session_pid(self, require_connection):
        require_connection.return_value = (self.connection, None)

        response = terminate_active_session(self.request(0))

        self.assertEqual(response.status_code, 400)
        self.assertIn("некорректный PID", json.loads(response.content)["message"])

    @patch("db_statistics.views._fetch_db_row", return_value=None)
    @patch("db_statistics.views._require_payload_connection")
    def test_returns_not_found_when_session_has_ended(self, require_connection, _fetch_row):
        require_connection.return_value = (self.connection, None)

        response = terminate_active_session(self.request(4321))

        self.assertEqual(response.status_code, 404)
