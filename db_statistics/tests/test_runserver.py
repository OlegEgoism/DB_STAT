from unittest import mock

from django.contrib.staticfiles.management.commands.runserver import Command as StaticfilesRunserverCommand
from django.core.management import get_commands
from django.core.management.commands.runserver import Command as CoreRunserverCommand
from django.test import SimpleTestCase

from db_statistics.management.commands.runserver import Command, recover_jobs_on_start, should_recover_on_start

COMMAND_MODULE = "db_statistics.management.commands.runserver"


class RunserverCommandTests(SimpleTestCase):
    def test_command_subclasses_core_runserver(self):
        self.assertTrue(issubclass(Command, CoreRunserverCommand))
        self.assertTrue(issubclass(Command, StaticfilesRunserverCommand))

    def test_db_statistics_runserver_overrides_builtin_command(self):
        # Регрессия: порядок INSTALLED_APPS должен выбирать нашу команду, иначе recovery не запускается.
        self.assertEqual(get_commands()["runserver"], "db_statistics")

    def test_serving_process_recovers(self):
        self.assertTrue(should_recover_on_start({"RUN_MAIN": "true"}, use_reloader=True))

    def test_reloader_parent_process_does_not_recover(self):
        self.assertFalse(should_recover_on_start({}, use_reloader=True))

    def test_noreload_single_process_recovers(self):
        self.assertTrue(should_recover_on_start({}, use_reloader=False))

    def test_run_main_with_noreload_recovers(self):
        self.assertTrue(should_recover_on_start({"RUN_MAIN": "true"}, use_reloader=False))

    def test_run_main_other_values_do_not_count_as_serving_process(self):
        self.assertFalse(should_recover_on_start({"RUN_MAIN": "false"}, use_reloader=True))

    @mock.patch(f"{COMMAND_MODULE}.call_command", side_effect=RuntimeError("БД недоступна"))
    def test_recovery_failure_is_logged_and_not_fatal(self, _call_command):
        with self.assertLogs(COMMAND_MODULE, level="WARNING") as logs:
            recover_jobs_on_start()

        self.assertTrue(any("восстановить" in line for line in logs.output))

    @mock.patch(f"{COMMAND_MODULE}.should_recover_on_start", return_value=True)
    @mock.patch(f"{COMMAND_MODULE}.call_command")
    @mock.patch.object(StaticfilesRunserverCommand, "handle")
    def test_handle_recovers_before_starting_server(self, base_handle, call_command, _should):
        calls = mock.Mock()
        calls.attach_mock(call_command, "recover")
        calls.attach_mock(base_handle, "serve")

        Command().handle(use_reloader=True, addrport="")

        self.assertEqual([name for name, *_ in calls.mock_calls], ["recover", "serve"])
        call_command.assert_called_once_with("recover_maintenance_jobs")

    @mock.patch(f"{COMMAND_MODULE}.should_recover_on_start", return_value=False)
    @mock.patch(f"{COMMAND_MODULE}.call_command")
    @mock.patch.object(StaticfilesRunserverCommand, "handle")
    def test_handle_skips_recovery_in_reloader_parent(self, base_handle, call_command, _should):
        Command().handle(use_reloader=True, addrport="")

        call_command.assert_not_called()
        base_handle.assert_called_once()
