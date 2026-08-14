from django.test import SimpleTestCase, override_settings

from db_statistics.view_helpers import _normalize_database_host


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
