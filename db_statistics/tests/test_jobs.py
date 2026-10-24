from unittest import mock

from django.core.management import call_command
from django.test import TestCase

from db_statistics.apps import _resubmit_queued_jobs
from db_statistics.models import DBConnection, MaintenanceJob, ReportJob


def _connection():
    return DBConnection.objects.create(name="target", host="db.internal", port=5432, database="app", username="reader", password="pw")


class StartupSweepTests(TestCase):
    def setUp(self):
        self.connection = _connection()

    @mock.patch("db_statistics.views.maintenance._submit_maintenance_job")
    @mock.patch("db_statistics.views.reports._submit_report_job")
    @mock.patch("db_statistics.job_locks.job_owner_alive", return_value=True)
    def test_startup_sweep_keeps_running_jobs_with_live_owner(self, _alive, submit_report, submit_maintenance):
        running = MaintenanceJob.objects.create(connection=self.connection, operation="vacuum", schema_name="s", table_name="t", status="running")
        running_report = ReportJob.objects.create(connection=self.connection, status="running")

        _resubmit_queued_jobs()

        running.refresh_from_db()
        running_report.refresh_from_db()
        self.assertEqual(running.status, "running")
        self.assertEqual(running_report.status, "running")
        submit_maintenance.assert_not_called()
        submit_report.assert_not_called()

    @mock.patch("db_statistics.views.maintenance._submit_maintenance_job")
    @mock.patch("db_statistics.views.reports._submit_report_job")
    def test_startup_sweep_submits_queued_jobs(self, submit_report, submit_maintenance):
        queued = MaintenanceJob.objects.create(connection=self.connection, operation="analyze", schema_name="s", table_name="t", status="queued")
        queued_report = ReportJob.objects.create(connection=self.connection, status="queued")

        _resubmit_queued_jobs()

        submit_maintenance.assert_called_once_with(queued.pk)
        submit_report.assert_called_once_with(queued_report.pk)


class RecoverCommandTests(TestCase):
    def setUp(self):
        self.connection = _connection()

    @mock.patch("db_statistics.views.reports._submit_report_job")
    @mock.patch("db_statistics.views.maintenance._submit_maintenance_job")
    def test_command_only_requeues_interrupted_jobs_without_submitting(self, submit_maintenance, submit_report):
        job = MaintenanceJob.objects.create(connection=self.connection, operation="vacuum", schema_name="s", table_name="t", status="running")
        report = ReportJob.objects.create(connection=self.connection, status="running")

        call_command("recover_maintenance_jobs", stdout=mock.Mock())

        job.refresh_from_db()
        report.refresh_from_db()
        self.assertEqual(job.status, "queued")
        self.assertEqual(report.status, "queued")
        submit_maintenance.assert_not_called()
        submit_report.assert_not_called()


class OrphanedJobSweepTests(TestCase):
    def setUp(self):
        self.connection = _connection()

    @mock.patch("db_statistics.views.maintenance._submit_maintenance_job")
    @mock.patch("db_statistics.views.reports._submit_report_job")
    @mock.patch("db_statistics.job_locks.job_owner_alive", return_value=False)
    def test_running_job_without_live_owner_is_requeued_and_submitted(self, _alive, submit_report, submit_maintenance):
        job = MaintenanceJob.objects.create(connection=self.connection, operation="vacuum", schema_name="s", table_name="t", status="running")

        _resubmit_queued_jobs()

        job.refresh_from_db()
        self.assertEqual(job.status, "queued")
        submit_maintenance.assert_called_once_with(job.pk)

    @mock.patch("db_statistics.views.maintenance._submit_maintenance_job")
    @mock.patch("db_statistics.views.reports._submit_report_job")
    @mock.patch("db_statistics.job_locks.job_owner_alive", return_value=True)
    def test_running_job_with_live_owner_is_left_alone(self, _alive, submit_report, submit_maintenance):
        job = MaintenanceJob.objects.create(connection=self.connection, operation="vacuum", schema_name="s", table_name="t", status="running")

        _resubmit_queued_jobs()

        job.refresh_from_db()
        self.assertEqual(job.status, "running")
        submit_maintenance.assert_not_called()
