from django.test import SimpleTestCase

from db_statistics.views import _validate_explain_query


class ValidateExplainQueryTests(SimpleTestCase):
    def test_accepts_select_and_removes_trailing_semicolon(self):
        query, error = _validate_explain_query(" SELECT * FROM public.orders; ")

        self.assertEqual(query, "SELECT * FROM public.orders")
        self.assertIsNone(error)

    def test_accepts_cte_select(self):
        query, error = _validate_explain_query("WITH recent AS (SELECT 1 AS id) SELECT * FROM recent")

        self.assertTrue(query.startswith("WITH recent"))
        self.assertIsNone(error)

    def test_rejects_multiple_statements(self):
        query, error = _validate_explain_query("SELECT 1; SELECT 2")

        self.assertIsNone(query)
        self.assertIn("одного SQL-запроса", error)

    def test_rejects_data_modification(self):
        query, error = _validate_explain_query("DELETE FROM public.orders")

        self.assertIsNone(query)
        self.assertIn("только для запросов SELECT", error)

    def test_rejects_empty_query(self):
        query, error = _validate_explain_query("  ")

        self.assertIsNone(query)
        self.assertEqual(error, "Введите SQL-запрос")
