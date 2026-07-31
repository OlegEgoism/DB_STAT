from django.test import SimpleTestCase

from db_statistics.views import _format_bytes, _memory_ratio, _memory_setting, _parse_pg_size_to_bytes


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

    def test_ratio_is_a_configuration_comparison_not_usage(self):
        value = _memory_setting("statement_mem", "Память запроса", "Лимит", "1GB", "kB")
        reference = _memory_setting("max_statement_mem", "Максимум", "Лимит", "4GB", "kB")

        self.assertEqual(
            _memory_ratio("Память запроса / максимум", value, reference),
            {"label": "Память запроса / максимум", "value": "1.00 ГБ", "reference": "4.00 ГБ", "ratio_percent": 25.0},
        )
