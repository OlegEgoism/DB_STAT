import io
from unittest import mock

from django.test import TestCase

from db_statistics.models import DBConnection, ReportJob
from db_statistics.views.reports import _run_report_job

FAILED_RU = "Блокировки"
FAILED_EN = "Locks"


def _fake_collect(failing_title):
    """Подмена _collect: один раздел не собирается (предупреждение), остальные собираются пустыми."""

    def collect(db_connection, title, query, params=None, language="ru"):
        if title == failing_title:
            return [], f"Не удалось собрать раздел «{title}»"
        return [], None

    return collect


class ReportCompletenessTests(TestCase):
    def setUp(self):
        self.connection = DBConnection.objects.create(name="target", host="db.internal", port=5432, database="app", username="reader", password="pw")

    def _run(self, failing_title, language="ru"):
        job = ReportJob.objects.create(connection=self.connection, status="queued", language=language)
        with mock.patch("db_statistics.views.reports._collect", side_effect=_fake_collect(failing_title)), mock.patch("db_statistics.views.reports._build_pdf", return_value=io.BytesIO(b"%PDF-1.4")):
            _run_report_job(str(job.pk))
        job.refresh_from_db()
        return job

    def test_failed_section_is_named_in_message_and_job_stays_completed(self):
        job = self._run(FAILED_RU)

        self.assertEqual(job.status, "completed")
        self.assertEqual(job.message, f"Готов, но неполный: не собраны разделы: {FAILED_RU}")
        self.assertIsNotNone(job.content)

    def test_failed_section_message_is_english_for_english_report(self):
        job = self._run(FAILED_EN, language="en")

        self.assertEqual(job.status, "completed")
        self.assertEqual(job.message, f"Ready, but incomplete: sections not collected: {FAILED_EN}")

    def test_complete_report_keeps_success_message(self):
        job = self._run(failing_title=None)

        self.assertEqual(job.status, "completed")
        self.assertEqual(job.message, "PDF-отчёт готов к скачиванию")
