import json

from django.test import TestCase
from django.urls import reverse

from db_statistics.models import DBAudit, DBConnection, DBUser
from db_statistics.views import SESSION_USER_ID_KEY


class FavoritesAuditTests(TestCase):
    def setUp(self):
        self.user = DBUser.objects.create(login="analyst", email="analyst@example.com")
        self.connection = DBConnection.objects.create(name="Основная БД", host="db.example.com", database="analytics", username="monitor", password="secret")
        self.user.connections.add(self.connection)
        session = self.client.session
        session[SESSION_USER_ID_KEY] = self.user.pk
        session.save()

    def toggle_favorite(self):
        return self.client.post(
            reverse("favorites"),
            data=json.dumps({"id": self.connection.pk, "object_type": "table", "object_key": "public\u001fevents"}),
            content_type="application/json",
        )

    def test_adding_favorite_writes_audit_event(self):
        response = self.toggle_favorite()

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["is_favorite"])
        audit = DBAudit.objects.get(action_type="favorite_add")
        self.assertEqual(audit.username, self.user.login)
        self.assertIn("Подключение: Основная БД", audit.info)
        self.assertIn("Тип объекта: Таблица", audit.info)
        self.assertIn("Идентификатор объекта: public\u001fevents", audit.info)

    def test_removing_favorite_does_not_write_add_audit_event(self):
        self.toggle_favorite()
        DBAudit.objects.all().delete()

        response = self.toggle_favorite()

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["is_favorite"])
        self.assertFalse(DBAudit.objects.exists())
