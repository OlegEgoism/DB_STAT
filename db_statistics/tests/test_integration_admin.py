import json

from django.conf import settings

from db_statistics.models import DBAudit, DBFavorite, DBUser
from db_statistics.tests.pg_base import PASSWORD, SCHEMA, PostgresTestCase


class AdminActionsIntegrationTests(PostgresTestCase):
    def _make_admin(self):
        admin = DBUser.objects.create_user(login="it_admin", email="it_admin@example.com", password=PASSWORD, role=settings.ADMIN_ROLE)
        admin.connections.add(self.connection)
        self.client.logout()
        self._login(admin.login)
        return admin

    def test_terminate_idle_in_transaction_session_as_admin_is_audited(self):
        self._make_admin()
        holder = self._target_connection()
        holder.autocommit = False
        try:
            with holder.cursor() as cursor:
                cursor.execute("SELECT pg_backend_pid()")
                holder_pid = cursor.fetchone()[0]
                cursor.execute("SELECT 1")
                cursor.fetchone()
            # Сессия открыта внутри транзакции и простаивает: именно такие объект терминирует вкладка.
            response = self.post_json("/transactions/terminate/", {"pid": holder_pid})
        finally:
            try:
                holder.close()
            except Exception:
                pass

        self.assertEqual(response.status_code, 200, response.content)
        self.assertTrue(json.loads(response.content)["ok"])
        self.assertTrue(DBAudit.objects.filter(action_type="transaction_terminate").exists())

    def test_terminate_requires_admin_role(self):
        response = self.post_json("/transactions/terminate/", {"pid": 1})

        self.assertEqual(response.status_code, 403)

    def test_audit_events_are_admin_only(self):
        response = self.client.get("/audit/events/")

        self.assertEqual(response.status_code, 403)

    def test_audit_events_for_admin_return_rows(self):
        self._make_admin()
        self.post_json("/tables/sizes/")

        response = self.client.get("/audit/events/")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(json.loads(response.content)["ok"])


class TempTableDeleteIntegrationTests(PostgresTestCase):
    def test_admin_drops_temp_table_of_another_session(self):
        self._make_admin_session()
        holder = self._target_connection()
        try:
            with holder.cursor() as cursor:
                cursor.execute("CREATE TEMP TABLE dbstat_it_temp (id int)")
                cursor.execute("SELECT n.nspname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace WHERE c.relname = 'dbstat_it_temp'")
                temp_schema = cursor.fetchone()[0]
            response = self.post_json("/temp-tables/delete/", {"schema_name": temp_schema, "table_name": "dbstat_it_temp"})
        finally:
            holder.close()

        self.assertEqual(response.status_code, 200, response.content)
        self.assertTrue(json.loads(response.content)["ok"])

    def _make_admin_session(self):
        admin = DBUser.objects.create_user(login="it_admin_temp", email="it_admin_temp@example.com", password=PASSWORD, role=settings.ADMIN_ROLE)
        admin.connections.add(self.connection)
        self.client.logout()
        self._login(admin.login)


class FavoritesApiIntegrationTests(PostgresTestCase):
    def test_add_and_remove_favorite_table(self):
        key = f"{SCHEMA}\x1forders"
        added = self.post_json("/favorites/", {"object_type": "table", "object_key": key})
        self.assertTrue(json.loads(added.content)["is_favorite"])
        self.assertTrue(DBFavorite.objects.filter(user=self.user, connection=self.connection, object_key=key).exists())

        removed = self.post_json("/favorites/", {"object_type": "table", "object_key": key})

        self.assertFalse(json.loads(removed.content)["is_favorite"])
        self.assertFalse(DBFavorite.objects.filter(user=self.user, connection=self.connection, object_key=key).exists())

    def test_favorites_list_returns_saved_items(self):
        DBFavorite.objects.create(user=self.user, connection=self.connection, object_type="schema", object_key=SCHEMA)

        response = self.client.get(f"/favorites/?id={self.connection.pk}")

        self.assertEqual(response.status_code, 200)
        self.assertIn({"object_type": "schema", "object_key": SCHEMA}, json.loads(response.content)["favorites"])


class MonitoringOverviewIntegrationTests(PostgresTestCase):
    def test_memory_overview_is_ok(self):
        data = self.post_json("/memory/overview/").json()

        self.assertTrue(data["ok"])

    def test_maintenance_stats_is_ok(self):
        data = self.post_json("/maintenance/stats/").json()

        self.assertTrue(data["ok"])
