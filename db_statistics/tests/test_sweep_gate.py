import sys
from unittest import mock

from django.test import SimpleTestCase

from db_statistics.apps import _runs_background_sweep


class BackgroundSweepGateTests(SimpleTestCase):
    def _argv(self, argv):
        return mock.patch.object(sys, "argv", argv)

    def test_one_off_management_command_does_not_run_sweep(self):
        with self._argv(["/app/manage.py", "shell"]), mock.patch("db_statistics.apps._running_tests", return_value=False):
            self.assertFalse(_runs_background_sweep())

    def test_runserver_runs_sweep(self):
        with self._argv(["/app/manage.py", "runserver"]), mock.patch("db_statistics.apps._running_tests", return_value=False):
            self.assertTrue(_runs_background_sweep())

    def test_gunicorn_process_runs_sweep(self):
        with self._argv(["/usr/local/bin/gunicorn", "db.wsgi:application"]), mock.patch("db_statistics.apps._running_tests", return_value=False):
            self.assertTrue(_runs_background_sweep())

    def test_test_run_does_not_run_sweep(self):
        with self._argv(["manage.py", "test"]):
            self.assertFalse(_runs_background_sweep())
