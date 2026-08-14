import os
from unittest.mock import patch

from django.template.loader import render_to_string
from django.test import SimpleTestCase, override_settings

from db.settings import _local_database_host
from db_statistics.view_helpers import _connection_kwargs, _normalize_database_host


class DatabaseHostNormalizationTests(SimpleTestCase):
    def test_container_uses_host_alias_without_explicit_environment_variable(self):
        with patch.dict(os.environ, {}, clear=True), patch(
            "db.settings.Path.exists", return_value=True
        ):
            self.assertEqual(_local_database_host(), "host.docker.internal")

    def test_explicit_host_override_has_priority(self):
        with patch.dict(os.environ, {"LOCAL_DATABASE_HOST": "gateway.example"}):
            self.assertEqual(_local_database_host(), "gateway.example")

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


class ConnectionFormHostTests(SimpleTestCase):
    def test_localhost_is_rendered_in_connection_form(self):
        html = render_to_string("includes/_modals.html")

        self.assertIn('id="connHost" placeholder="localhost" value="localhost"', html)
        self.assertNotIn('value="host.docker.internal"', html)
