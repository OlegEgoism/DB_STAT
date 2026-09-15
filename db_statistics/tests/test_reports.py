from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from db_statistics.views.reports import _recommendations, _report_sections


class DatabaseReportTests(SimpleTestCase):
    @patch("db_statistics.views.reports._collect", return_value=([], None))
    def test_schema_size_query_groups_every_non_aggregate_owner_column(self, collect):
        _report_sections(SimpleNamespace(is_greenplum_compatible=False))

        schema_query = next(call.args[2] for call in collect.call_args_list if call.args[1] == "Размеры схем")
        self.assertIn("GROUP BY namespace.nspname, namespace.nspowner", schema_query)

    def test_recommendations_include_partial_report_warning(self):
        sections = [{"title": "Блокировки", "rows": [], "warning": None}, {"title": "Временные таблицы", "rows": [], "warning": None}, {"title": "Обслуживание", "rows": [], "warning": "Недоступно"}]

        recommendations = _recommendations(sections)

        self.assertIn(("Информация", "Часть разделов недоступна: Обслуживание."), recommendations)
