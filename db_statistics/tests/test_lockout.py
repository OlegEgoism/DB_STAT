from datetime import timedelta
from unittest import mock

from django.conf import settings
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from db_statistics.auth_backends import LockoutAwareModelBackend, clear_login_failures, register_failed_login
from db_statistics.models import DBAudit, DBUser

PASSWORD = "correct-horse-battery"


@override_settings(LOGIN_MAX_FAILED_ATTEMPTS=3, LOGIN_LOCKOUT_SECONDS=600)
class LoginLockoutTests(TestCase):
    def setUp(self):
        self.user = DBUser.objects.create_user(login="analyst", email="analyst@example.com", password=PASSWORD)

    def _post_login(self, password):
        return self.client.post(reverse("login"), {"identifier": "analyst", "password": password, "session_duration": "1"})

    def test_register_failed_login_locks_after_threshold(self):
        for expected_attempt in (1, 2):
            attempt, lockout_until = register_failed_login(self.user)
            self.assertEqual(attempt, expected_attempt)
            self.assertIsNone(lockout_until)

        attempt, lockout_until = register_failed_login(self.user)

        self.assertEqual(attempt, 3)
        self.assertIsNotNone(lockout_until)
        self.user.refresh_from_db()
        self.assertEqual(self.user.failed_login_attempts, 0)
        self.assertGreater(self.user.lockout_until, timezone.now())

    def test_clear_login_failures_resets_counter_and_lockout(self):
        register_failed_login(self.user)

        clear_login_failures(self.user)

        self.user.refresh_from_db()
        self.assertEqual(self.user.failed_login_attempts, 0)
        self.assertIsNone(self.user.lockout_until)

    def test_admin_backend_refuses_user_locked_by_login_form(self):
        for _ in range(settings.LOGIN_MAX_FAILED_ATTEMPTS):
            self._post_login("wrong-password")

        self.user.refresh_from_db()
        self.assertGreater(self.user.lockout_until, timezone.now())
        # Даже верный пароль не пускает, пока блокировка действует — в том числе через Django admin.
        self.assertIsNone(LockoutAwareModelBackend().authenticate(None, username="analyst", password=PASSWORD))

    def test_login_form_refuses_correct_password_during_lockout(self):
        DBUser.objects.filter(pk=self.user.pk).update(lockout_until=timezone.now() + timedelta(minutes=5))

        response = self._post_login(PASSWORD)

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertFalse(self.client.session.get(settings.SESSION_USER_ID_KEY))

    def test_failed_login_form_attempt_is_audited_with_attempt_number(self):
        self._post_login("wrong-password")

        audit = DBAudit.objects.filter(action_type="login").latest("created")
        self.assertIn("попытка №1", audit.info)

    def test_successful_login_clears_previous_failures(self):
        register_failed_login(self.user)

        response = self._post_login(PASSWORD)

        self.assertRedirects(response, reverse("home"), fetch_redirect_response=False)
        self.user.refresh_from_db()
        self.assertEqual(self.user.failed_login_attempts, 0)

    def test_backend_does_not_lock_when_lockout_window_already_passed(self):
        DBUser.objects.filter(pk=self.user.pk).update(lockout_until=timezone.now() - timedelta(seconds=1))

        with mock.patch("db_statistics.auth_backends.timezone.now", return_value=timezone.now()):
            user = LockoutAwareModelBackend().authenticate(None, username="analyst", password=PASSWORD)

        self.assertEqual(user, self.user)
