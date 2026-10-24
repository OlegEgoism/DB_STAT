from db_statistics.models import DBFavorite
from db_statistics.tests.pg_base import SCHEMA, PostgresTestCase


def _names(items, key="table_name"):
    return {item[key] for item in items}


class TableListIntegrationTests(PostgresTestCase):
    def test_table_list_contains_seeded_tables(self):
        response = self.post_json("/tables/sizes/")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["ok"])
        ours = {(t["schema_name"], t["table_name"]) for t in data["tables"]}
        self.assertTrue({(SCHEMA, "orders"), (SCHEMA, "documents"), (SCHEMA, "small")} <= ours)

    def test_search_narrows_results_to_matching_table(self):
        data = self.post_json("/tables/sizes/", {"search": "orders"}).json()

        self.assertEqual(data["total_count"], 1)
        self.assertEqual(data["tables"][0]["table_name"], "orders")

    def test_unknown_sort_key_is_ignored_not_injected(self):
        response = self.post_json("/tables/sizes/", {"sort": "table_name; DROP TABLE dbstat_it.orders"})

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])
        # Таблица на месте: инъекция через сортировку не сработала.
        self.assertTrue(self.post_json("/tables/sizes/", {"search": "orders"}).json()["total_count"] == 1)

    def test_pagination_returns_requested_page_size_and_total(self):
        data = self.post_json("/tables/sizes/", {"page": 1, "page_size": 10}).json()

        self.assertEqual(data["page_size"], 10)
        self.assertGreaterEqual(data["total_count"], 3)
        self.assertLessEqual(len(data["tables"]), 10)

    def test_schema_list_includes_seeded_schema(self):
        data = self.post_json("/databases/schemas/").json()

        self.assertTrue(data["ok"])
        self.assertIn(SCHEMA, {schema["schema_name"] for schema in data["schemas"]})


class ToastListIntegrationTests(PostgresTestCase):
    def test_toast_list_contains_table_with_out_of_line_values(self):
        data = self.post_json("/toast-tables/sizes/").json()

        self.assertTrue(data["ok"])
        names = {(t["schema_name"], t["table_name"]) for t in data["toast_tables"]}
        self.assertIn((SCHEMA, "documents"), names)

    def test_toast_list_excludes_table_with_empty_toast_table(self):
        # orders имеет TEXT-столбец, поэтому TOAST-таблица у неё есть, но она пуста.
        data = self.post_json("/toast-tables/sizes/", {"search": "orders"}).json()

        self.assertEqual(data["total_count"], 0)

    def test_toast_list_excludes_table_without_toast_table(self):
        # small не содержит TEXT/JSONB и TOAST-таблицы не имеет вовсе.
        data = self.post_json("/toast-tables/sizes/", {"search": "small"}).json()

        self.assertEqual(data["total_count"], 0)

    def test_toast_share_is_a_percentage(self):
        data = self.post_json("/toast-tables/sizes/", {"search": "documents"}).json()

        share = data["toast_tables"][0]["toast_share"]
        self.assertGreaterEqual(share, 0)
        self.assertLessEqual(share, 100)

    def test_favorites_filter_shows_only_starred_table(self):
        DBFavorite.objects.create(user=self.user, connection=self.connection, object_type="table", object_key=f"{SCHEMA}\x1fdocuments")

        data = self.post_json("/toast-tables/sizes/", {"favorites_only": True}).json()

        self.assertEqual([t["table_name"] for t in data["toast_tables"]], ["documents"])


class ConnectionAccessIntegrationTests(PostgresTestCase):
    def test_connection_not_assigned_to_user_is_not_found(self):
        other = self._make_connection(name="not-mine", password=self.target["password"])
        other_user = self.user
        other_user.connections.remove(other)

        response = self.post_json("/tables/sizes/", connection=other)

        self.assertEqual(response.status_code, 404)

    def test_wrong_password_returns_safe_error_without_db_details(self):
        broken = self._make_connection(name="wrong-password", password="definitely-wrong")
        self.user.connections.add(broken)

        response = self.post_json("/tables/sizes/", connection=broken)

        self.assertEqual(response.status_code, 400)
        body = response.json()
        self.assertFalse(body["ok"])
        self.assertIn("журнале", body["message"])
        self.assertNotIn("password authentication", body["message"])
        self.assertNotIn(self.target["user"], body["message"])


class MonitoringIntegrationTests(PostgresTestCase):
    def test_active_sessions_endpoint_returns_rows(self):
        data = self.post_json("/sessions/active/").json()

        self.assertTrue(data["ok"])
        self.assertIn("sessions", data)

    def test_active_queries_endpoint_returns_rows(self):
        data = self.post_json("/queries/active/").json()

        self.assertTrue(data["ok"])
        self.assertIn("queries", data)

    def test_blocking_locks_endpoint_returns_rows(self):
        data = self.post_json("/locks/blocking/").json()

        self.assertTrue(data["ok"])
        self.assertIn("locks", data)
