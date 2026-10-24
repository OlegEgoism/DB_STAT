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
    def test_startup_sweep_never_resets_running_jobs(self, submit_report, submit_maintenance):
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

    @mock.patch("db_statistics.management.commands.recover_maintenance_jobs._submit_report_job")
    @mock.patch("db_statistics.management.commands.recover_maintenance_jobs._submit_maintenance_job")
    def test_command_requeues_and_resubmits_interrupted_jobs(self, submit_maintenance, submit_report):
        job = MaintenanceJob.objects.create(connection=self.connection, operation="vacuum", schema_name="s", table_name="t", status="running")
        report = ReportJob.objects.create(connection=self.connection, status="running")

        call_command("recover_maintenance_jobs", stdout=mock.Mock())

        job.refresh_from_db()
        report.refresh_from_db()
        self.assertEqual(job.status, "queued")
        self.assertEqual(report.status, "queued")
        submit_maintenance.assert_called_once_with(job.pk)
        submit_report.assert_called_once_with(report.pk)
