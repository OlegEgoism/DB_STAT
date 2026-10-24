from db_statistics.tests.pg_base import SCHEMA, PostgresTestCase


class ViewsAndFunctionsIntegrationTests(PostgresTestCase):
    def test_views_list_contains_ordinary_and_materialized_views(self):
        data = self.post_json("/views/list/", {"search": "orders"}).json()

        self.assertTrue(data["ok"])
        names = {(v["schema_name"], v["view_name"]) for v in data["views"]}
        self.assertIn((SCHEMA, "v_orders"), names)
        self.assertIn((SCHEMA, "mv_orders"), names)

    def test_views_list_filter_by_type(self):
        ordinary = self.post_json("/views/list/", {"search": "orders", "view_type": "ordinary"}).json()
        materialized = self.post_json("/views/list/", {"search": "orders", "view_type": "materialized"}).json()

        self.assertEqual({v["view_name"] for v in ordinary["views"]}, {"v_orders"})
        self.assertEqual({v["view_name"] for v in materialized["views"]}, {"mv_orders"})

    def test_functions_list_contains_seeded_function(self):
        data = self.post_json("/functions/list/", {"search": "f_orders"}).json()

        self.assertTrue(data["ok"])
        self.assertIn("f_orders_count", {f["function_name"] for f in data["functions"]})


class GreenplumOnlyIntegrationTests(PostgresTestCase):
    """Распределение строк по сегментам существует только в Greenplum/Greengage.

    На PostgreSQL эти эндпоинты обязаны отвечать 400 с понятным сообщением, а не падать.
    Сам SQL для Greenplum на тестовом стенде не проверяется.
    """

    def test_distribution_tables_is_greenplum_only(self):
        response = self.post_json("/distribution/tables/")

        self.assertEqual(response.status_code, 400)
        self.assertIn("Greenplum", response.json()["message"])

    def test_distribution_info_is_greenplum_only(self):
        response = self.post_json("/distribution/info/", {"schema_name": SCHEMA, "table_name": "orders"})

        self.assertEqual(response.status_code, 400)
        self.assertIn("Greenplum", response.json()["message"])


class TempTablesIntegrationTests(PostgresTestCase):
    def test_temp_tables_list_is_ok_when_none_exist(self):
        data = self.post_json("/temp-tables/sizes/").json()

        self.assertTrue(data["ok"])
        self.assertEqual(data["temp_tables"], [])

    def test_delete_temp_table_requires_admin(self):
        response = self.post_json("/temp-tables/delete/", {"schema_name": SCHEMA, "table_name": "orders"})

        self.assertEqual(response.status_code, 403)
