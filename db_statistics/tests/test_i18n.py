import io
import json
from datetime import timedelta
from unittest import mock

from django.conf import settings
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone, translation
from django.utils.translation import gettext

from db_statistics.models import DBConnection, DBUser, ReportJob
from db_statistics.views.additional import _lockout_message
from db_statistics.views.reports import _report_sections, _run_report_job

PASSWORD = "correct-horse-battery"


class EnglishCatalogTests(TestCase):
    """Русский текст — исходный msgid, английский берётся из django.mo."""

    def test_english_catalog_translates_login_error(self):
        with translation.override("en"):
            self.assertEqual(gettext("Неверный логин, почта или пароль"), "Invalid login, email or password")

    def test_russian_text_is_returned_unchanged_by_default(self):
        with translation.override("ru"):
            self.assertEqual(gettext("Неверный логин, почта или пароль"), "Неверный логин, почта или пароль")

    def test_lockout_message_follows_active_language(self):
        lockout_until = timezone.now() + timedelta(minutes=5)
        with translation.override("en"):
            self.assertEqual(_lockout_message(lockout_until), "Too many failed attempts. Try again in 5 min.")
        with translation.override("ru"):
            self.assertEqual(_lockout_message(lockout_until), "Слишком много неверных попыток. Повторите через 5 мин.")

    def test_greenplum_fallback_status_is_separate_from_state_headers(self):
        connection = DBConnection(name="target", host="db.internal", port=5432, database="app", username="reader", db_type="PostgreSQL")
        with mock.patch("db_statistics.views.reports._collect", return_value=([], None)):
            with translation.override("en"):
                english = {section["title"]: section for section in _report_sections(connection)}
            with translation.override("ru"):
                russian = {section["title"]: section for section in _report_sections(connection)}
        self.assertEqual(english["Active queries"]["headers"][2], "State")
        self.assertEqual(english["Greenplum/Greengage segments"]["headers"], ["Status"])
        self.assertEqual(russian["Сегменты Greenplum/Greengage"]["headers"], ["Состояние"])


class LoginLanguageTests(TestCase):
    def setUp(self):
        self.user = DBUser.objects.create_user(login="analyst", email="analyst@example.com", password=PASSWORD)

    def _post_login(self, accept_language, **fields):
        data = {"identifier": "analyst", "password": "wrong-password", "session_duration": "1", **fields}
        return self.client.post(reverse("login"), data, HTTP_ACCEPT_LANGUAGE=accept_language)

    def test_wrong_password_message_is_english_for_english_request(self):
        response = self._post_login("en")

        self.assertContains(response, "Invalid login, email or password")
        self.assertNotContains(response, "Неверный логин")

    def test_wrong_password_message_is_russian_for_russian_request(self):
        response = self._post_login("ru")

        self.assertContains(response, "Неверный логин, почта или пароль")
        self.assertNotContains(response, "Invalid login")

    def test_session_duration_error_is_english_for_english_request(self):
        response = self._post_login("en", session_duration="0")

        self.assertContains(response, f"Session duration must be between {settings.MIN_SESSION_DURATION_MINUTES} minutes and {settings.MAX_SESSION_DURATION_HOURS} hours")

    def test_lockout_message_is_english_for_english_request(self):
        DBUser.objects.filter(pk=self.user.pk).update(lockout_until=timezone.now() + timedelta(minutes=5))

        response = self._post_login("en", password=PASSWORD)

        self.assertContains(response, "Too many failed attempts. Try again in 5 min.")

    def test_unsupported_language_error_is_english_for_english_request(self):
        response = self.client.post(reverse("language_settings"), json.dumps({"language": "de"}), content_type="application/json", HTTP_ACCEPT_LANGUAGE="en")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["message"], "Only RU and EN languages are supported")


class ReportLanguageTests(TestCase):
    def setUp(self):
        self.connection = DBConnection.objects.create(name="target", host="db.internal", port=5432, database="app", username="reader", password="pw")

    def test_successful_english_report_has_english_message(self):
        job = ReportJob.objects.create(connection=self.connection, status="queued", language="en")

        with mock.patch("db_statistics.views.reports._collect", return_value=([], None)), mock.patch("db_statistics.views.reports._build_pdf", return_value=io.BytesIO(b"%PDF-1.4")):
            _run_report_job(str(job.pk))

        job.refresh_from_db()
        self.assertEqual(job.status, "completed")
        self.assertEqual(job.message, "PDF report is ready for download")
