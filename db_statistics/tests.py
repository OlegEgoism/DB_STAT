import json
from types import SimpleNamespace
from unittest.mock import patch

from django.test import RequestFactory, SimpleTestCase

from db_statistics.views_administration import runtime_memory_usage


class RuntimeMemoryUsageTests(SimpleTestCase):
    def setUp(self):
        self.request = RequestFactory().post(
            "/memory/runtime/",
            data=json.dumps({"id": 1}),
            content_type="application/json",
        )
        self.connection = SimpleNamespace(id=1)

    @patch("db_statistics.views_administration._fetch_db_rows")
    @patch("db_statistics.views_administration._require_payload_connection")
    def test_returns_cgroup_memory_for_groups_and_active_users(self, require_connection, fetch_rows):
        require_connection.return_value = (self.connection, None)
        fetch_rows.side_effect = [
            [(6438, "rg_analysts", "sdw1", 12.5, 256, 2048, 10)],
            [("analyst_1", "rg_analysts", 2, 3, 256)],
            [(6438, "rg_analysts", 2, 1)],
        ]

        response = runtime_memory_usage(self.request)
        payload = json.loads(response.content)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["total_memory"], "256.00 МБ")
        self.assertEqual(payload["groups"][0]["running"], 2)
        self.assertEqual(payload["groups"][0]["queueing"], 1)
        self.assertEqual(payload["users"][0]["shared_group_memory"], "256.00 МБ")

    @patch("db_statistics.views_administration._fetch_db_rows", side_effect=RuntimeError("view missing"))
    @patch("db_statistics.views_administration._require_payload_connection")
    def test_reports_greenplum_view_error(self, require_connection, _fetch_rows):
        require_connection.return_value = (self.connection, None)

        response = runtime_memory_usage(self.request)
        payload = json.loads(response.content)

        self.assertEqual(response.status_code, 400)
        self.assertFalse(payload["ok"])
        self.assertIn("resource groups", payload["message"])
