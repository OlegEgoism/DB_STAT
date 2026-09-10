import json
from unittest.mock import patch

import psycopg2
from django.conf import settings
from django.test import TestCase
from django.urls import reverse

from db_statistics.models import DBAudit, DBUser


class ConnectionViewTests(TestCase):
    def setUp(self):
        self.user = DBUser.objects.create_superuser("admin", "admin@example.com", "test-password")
        session = self.client.session
        session[settings.SESSION_USER_ID_KEY] = self.user.pk
        session.save()
        self.payload = {"name": "Production", "host": "database.internal", "port": 5432, "database": "postgres", "user": "monitor", "password": "secret"}

    def test_create_rejects_invalid_port(self):
        self.payload["port"] = "not-a-port"

        response = self.client.post(reverse("connections"), data=json.dumps(self.payload), content_type="application/json")

        self.assertEqual(response.status_code, 400)
        self.assertIn("от 1 до 65535", response.json()["message"])

    @patch("db_statistics.views_additional._test_connection_params")
    def test_connection_error_does_not_expose_driver_details(self, test_connection):
        test_connection.side_effect = psycopg2.OperationalError("password authentication failed for secret-user")

        response = self.client.post(reverse("test_connection"), data=json.dumps(self.payload), content_type="application/json")

        self.assertEqual(response.status_code, 400)
        self.assertNotIn("secret-user", response.json()["message"])
        self.assertNotIn("secret-user", DBAudit.objects.get().info)
