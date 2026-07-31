from django.test import SimpleTestCase

from db_statistics.views import _format_bytes, _parse_pg_size_to_bytes


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
