import json
from unittest import mock

from db_statistics.models import ReportJob
from db_statistics.tests.pg_base import PostgresTestCase
from db_statistics.views.reports import _run_report_job


class PdfReportIntegrationTests(PostgresTestCase):
    def test_report_job_builds_real_pdf_with_sections(self):
        with mock.patch("db_statistics.views.reports._submit_report_job") as submit:
            response = self.post_json("/reports/database.pdf")
        self.assertEqual(response.status_code, 202, response.content)
        job_id = json.loads(response.content)["job"]["id"]
        submit.assert_called_once()

        # Выполняем задачу синхронно, а не через пул потоков: тест должен быть детерминированным.
        _run_report_job(job_id)

        job = ReportJob.objects.get(pk=job_id)
        self.assertEqual(job.status, "completed", job.message)
        self.assertTrue(bytes(job.content).startswith(b"%PDF"))
        self.assertGreater(len(bytes(job.content)), 2000)
