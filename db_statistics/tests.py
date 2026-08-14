from django.test import SimpleTestCase, override_settings

from db_statistics.view_helpers import _database_connection_error_message, _normalize_database_host


class NormalizeDatabaseHostTests(SimpleTestCase):
    @override_settings(LOCALHOST_DB_HOST="host.docker.internal")
    def test_localhost_uses_configured_database_host(self):
        self.assertEqual(_normalize_database_host("localhost"), "host.docker.internal")
        self.assertEqual(_normalize_database_host("LOCALHOST"), "host.docker.internal")

    @override_settings(LOCALHOST_DB_HOST="host.docker.internal")
    def test_ipv6_loopback_uses_configured_database_host(self):
        self.assertEqual(_normalize_database_host("::1"), "host.docker.internal")

    @override_settings(LOCALHOST_DB_HOST="host.docker.internal")
    def test_remote_host_is_not_changed(self):
        self.assertEqual(_normalize_database_host("db.example.com"), "db.example.com")


class DatabaseConnectionErrorMessageTests(SimpleTestCase):
    def test_localhost_error_contains_linux_network_hint(self):
        message = _database_connection_error_message(
            "Local DB", "localhost", "connection refused"
        )

        self.assertIn("connection refused", message)
        self.assertIn("--network host", message)
        self.assertIn("pg_hba.conf", message)

    def test_remote_host_error_does_not_contain_local_hint(self):
        message = _database_connection_error_message(
            "Remote DB", "db.example.com", "connection refused"
        )

        self.assertEqual(
            message,
            "Не удалось подключиться к Remote DB: connection refused",
        )
