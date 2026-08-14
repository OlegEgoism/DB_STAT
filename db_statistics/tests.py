from django.test import SimpleTestCase, override_settings

from db_statistics.view_helpers import _connection_kwargs, _normalize_database_host


class DatabaseHostNormalizationTests(SimpleTestCase):
    @override_settings(LOCAL_DATABASE_HOST="host.docker.internal")
    def test_container_loopback_addresses_use_docker_host_alias(self):
        for host in ("localhost", "127.0.0.1", "::1", " LOCALHOST "):
            with self.subTest(host=host):
                self.assertEqual(_normalize_database_host(host), "host.docker.internal")

    @override_settings(LOCAL_DATABASE_HOST="")
    def test_native_loopback_address_is_unchanged(self):
        self.assertEqual(_normalize_database_host("127.0.0.1"), "127.0.0.1")

    @override_settings(LOCAL_DATABASE_HOST="host.docker.internal")
    def test_remote_database_address_is_unchanged(self):
        self.assertEqual(_normalize_database_host("postgres.example.com"), "postgres.example.com")

    @override_settings(LOCAL_DATABASE_HOST="host.docker.internal")
    def test_connection_kwargs_use_normalized_host(self):
        params = _connection_kwargs("localhost", 5432, "postgres", "postgres", "secret")
        self.assertEqual(params["host"], "host.docker.internal")
