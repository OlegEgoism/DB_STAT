from unittest.mock import patch

from django.test import SimpleTestCase

from db_statistics.views import _format_bytes, _greenplum_memory_item, _greenplum_runtime_memory, _memory_setting, _parse_pg_size_to_bytes


class PostgreSQLSizeHelpersTests(SimpleTestCase):
    def test_parses_explicit_units_with_and_without_spaces(self):
        self.assertEqual(_parse_pg_size_to_bytes("4 GB"), 4 * 1024**3)
        self.assertEqual(_parse_pg_size_to_bytes("125MB"), 125 * 1024**2)

    def test_uses_byte_as_the_default_unit(self):
        self.assertEqual(_parse_pg_size_to_bytes("65536"), 65536)

    def test_accepts_an_implicit_unit_for_greenplum_settings(self):
        size = _parse_pg_size_to_bytes("65536", default_unit="MB")

        self.assertEqual(size, 64 * 1024**3)
        self.assertEqual(_format_bytes(size), "64.00 ГБ")

    def test_accepts_postgresql_block_units(self):
        self.assertEqual(_parse_pg_size_to_bytes("16", default_unit="8kB"), 128 * 1024)

    def test_rejects_unknown_units_instead_of_treating_them_as_bytes(self):
        self.assertIsNone(_parse_pg_size_to_bytes("10 widgets"))


class MemoryOverviewHelpersTests(SimpleTestCase):
    def test_setting_uses_unit_reported_by_pg_settings(self):
        setting = _memory_setting("gp_vmem_protect_limit", "Лимит", "Защита OOM", "65536", "MB")

        self.assertEqual(setting["value"], "64.00 ГБ")
        self.assertEqual(setting["size_bytes"], 64 * 1024**3)

    def test_setting_can_use_a_database_specific_fallback_unit(self):
        setting = _memory_setting("gp_vmem_protect_limit", "Лимит", "Защита OOM", "65536", None, "MB")

        self.assertEqual(setting["value"], "64.00 ГБ")


class GreenplumRuntimeMemoryTests(SimpleTestCase):
    def test_builds_actual_usage_from_used_and_available_memory(self):
        self.assertEqual(
            _greenplum_memory_item("6438", "sdw1", 3072, 1024),
            {"group": "6438", "hostname": "sdw1", "used": "3.00 ГБ", "available": "1.00 ГБ", "limit": "4.00 ГБ", "usage_percent": 75.0, "limit_available": True},
        )

    def test_builds_usage_without_limit_for_older_greenplum(self):
        item = _greenplum_memory_item("6438", "sdw1", 3072, None)

        self.assertEqual(item["used"], "3.00 ГБ")
        self.assertIsNone(item["usage_percent"])
        self.assertFalse(item["limit_available"])

    @patch(
        "db_statistics.views._fetch_db_rows",
        side_effect=[[("groupid",), ("hostname",), ("memory_usage",)], [("default_group", "sdw1", 3072, None)]],
    )
    def test_reads_older_greenplum_view_without_memory_available(self, _fetch_rows):
        result = _greenplum_runtime_memory(object())

        self.assertTrue(result["supported"])
        self.assertEqual(result["source"], "gp_toolkit.gp_resgroup_status_per_host")
        self.assertFalse(result["has_limit_data"])
        self.assertEqual(result["items"][0]["used"], "3.00 ГБ")
