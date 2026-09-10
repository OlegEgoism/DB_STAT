import os
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase

from db_statistics.models import DBUser


class EnsureInitialAdminTests(TestCase):
    @patch.dict(os.environ, {"INITIAL_ADMIN_LOGIN": "owner", "INITIAL_ADMIN_EMAIL": "owner@example.com", "INITIAL_ADMIN_PASSWORD": "a-secure-test-password"}, clear=False)
    def test_creates_configured_admin_once(self):
        output = StringIO()

        call_command("ensure_initial_admin", stdout=output)
        call_command("ensure_initial_admin", stdout=output)

        user = DBUser.objects.get(login="owner")
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)
        self.assertTrue(user.check_password("a-secure-test-password"))
        self.assertEqual(DBUser.objects.count(), 1)
        self.assertIn("already exists", output.getvalue())

    @patch.dict(os.environ, {"INITIAL_ADMIN_PASSWORD": ""}, clear=False)
    @patch("db_statistics.management.commands.ensure_initial_admin.secrets.token_urlsafe", return_value="generated-password")
    def test_generates_password_when_not_configured(self, _token_urlsafe):
        output = StringIO()

        call_command("ensure_initial_admin", stdout=output)

        self.assertTrue(DBUser.objects.get(login="admin").check_password("generated-password"))
        self.assertIn("Generated one-time initial password: generated-password", output.getvalue())
