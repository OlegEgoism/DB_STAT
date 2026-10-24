from db_statistics.models import MaintenanceJob
from db_statistics.tests.pg_base import SCHEMA, PostgresTestCase
from db_statistics.views.maintenance import _run_maintenance_operation


class MaintenanceJobIntegrationTests(PostgresTestCase):
    def _run(self, operation):
        job = MaintenanceJob.objects.create(user=self.user, connection=self.connection, operation=operation, schema_name=SCHEMA, table_name="orders")
        # Выполняем синхронно: пул потоков в тесте не нужен, результат проверяется детерминированно.
        _run_maintenance_operation(str(job.pk))
        job.refresh_from_db()
        return job

    def test_analyze_job_completes_and_records_statistics(self):
        job = self._run("analyze")

        self.assertEqual(job.status, "completed", job.message)
        self.assertIsNotNone(job.statistics)

    def test_vacuum_job_completes(self):
        job = self._run("vacuum")

        self.assertEqual(job.status, "completed", job.message)

    def test_explain_analyze_job_returns_plan_lines(self):
        job = self._run("explain_analyze")

        self.assertEqual(job.status, "completed", job.message)
        self.assertTrue(job.details)
