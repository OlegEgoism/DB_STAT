from django.core.checks import WARNING
from django.test import SimpleTestCase, override_settings

from db_statistics.checks import check_connection_pool_budget


class ConnectionPoolBudgetCheckTests(SimpleTestCase):
    @override_settings(DB_CONNECTION_POOL_MAX_CONN=21)
    def test_warns_when_pool_max_conn_exceeds_20(self):
        messages = check_connection_pool_budget(None)

        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0].id, "db_statistics.W003")
        self.assertEqual(messages[0].level, WARNING)
        self.assertIn("DB_CONNECTION_POOL_MAX_CONN=21", messages[0].msg)

    @override_settings(DB_CONNECTION_POOL_MAX_CONN=20)
    def test_no_warning_at_threshold(self):
        self.assertEqual(check_connection_pool_budget(None), [])

    @override_settings(DB_CONNECTION_POOL_MAX_CONN=10)
    def test_no_warning_for_default_pool_size(self):
        self.assertEqual(check_connection_pool_budget(None), [])
