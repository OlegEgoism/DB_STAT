import json

from django.test import TestCase
from django.urls import reverse

from db_statistics.models import DBConnection, DBUser, UserSidebarSettings
from db_statistics.views import SESSION_USER_ID_KEY


class FavoritesSettingsTests(TestCase):
    def setUp(self):
        self.user = DBUser.objects.create(login="analyst", email="analyst@example.com")
        self.connection = DBConnection.objects.create(name="Main", host="db", database="postgres", username="postgres", password="secret")
        self.user.connections.add(self.connection)
        session = self.client.session
        session[SESSION_USER_ID_KEY] = self.user.pk
        session.save()

    def post_favorite(self, payload):
        return self.client.post(reverse("favorites_settings"), data=json.dumps(payload), content_type="application/json")

    def test_saves_connection_schema_and_table_favorites(self):
        response = self.post_favorite({"kind": "connection", "connection_id": self.connection.pk, "enabled": True})
        self.assertEqual(response.status_code, 200)
        response = self.post_favorite({"kind": "schema", "connection_id": self.connection.pk, "schema_name": "public", "enabled": True})
        self.assertEqual(response.status_code, 200)
        response = self.post_favorite({"kind": "table", "connection_id": self.connection.pk, "schema_name": "public", "table_name": "orders", "enabled": True})
        self.assertEqual(response.status_code, 200)
        settings = UserSidebarSettings.objects.get(user=self.user)
        self.assertEqual(settings.favorite_connections, [str(self.connection.pk)])
        self.assertEqual(settings.favorite_schemas, [{"connection_id": str(self.connection.pk), "schema_name": "public"}])
        self.assertEqual(settings.favorite_tables, [{"connection_id": str(self.connection.pk), "schema_name": "public", "table_name": "orders"}])

    def test_removes_schema_from_favorites(self):
        self.post_favorite({"kind": "schema", "connection_id": self.connection.pk, "schema_name": "analytics", "enabled": True})
        response = self.post_favorite({"kind": "schema", "connection_id": self.connection.pk, "schema_name": "analytics", "enabled": False})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["favorite_schemas"], [])

    def test_rejects_another_users_connection(self):
        unavailable = DBConnection.objects.create(name="Private", host="private", database="postgres", username="postgres", password="secret")
        response = self.post_favorite({"kind": "connection", "connection_id": unavailable.pk, "enabled": True})
        self.assertEqual(response.status_code, 404)

    def test_requires_login(self):
        self.client.session.flush()
        response = self.client.get(reverse("favorites_settings"))
        self.assertEqual(response.status_code, 401)
