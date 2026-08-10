import json
from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

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

    def test_removing_favorite_writes_audit_event(self):
        self.toggle_favorite()
        DBAudit.objects.all().delete()

        response = self.toggle_favorite()

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["is_favorite"])
        audit = DBAudit.objects.get(action_type="favorite_remove")
        self.assertEqual(audit.username, self.user.login)
        self.assertIn("Объект удалён из избранных объектов", audit.info)
        self.assertIn("Подключение: Основная БД", audit.info)
        self.assertIn("Тип объекта: Таблица", audit.info)
        self.assertIn("Идентификатор объекта: public\u001fevents", audit.info)


class AuditEventsTests(TestCase):
    def setUp(self):
        self.admin = DBUser.objects.create(login="admin", email="admin@example.com", role="Администратор")
        self.analyst = DBUser.objects.create(login="analyst", email="analyst@example.com")
        now = timezone.now()
        DBAudit.objects.create(username="analyst", action_type="login", info="Второе событие", created=now)
        DBAudit.objects.create(username="admin", action_type="connection_create", info="Первое событие", created=now - timedelta(minutes=1))
        session = self.client.session
        session[SESSION_USER_ID_KEY] = self.admin.pk
        session.save()

    def test_admin_can_filter_audit_by_user(self):
        response = self.client.get(reverse("audit_events"), {"username": "analyst"})

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["users"], ["admin", "analyst"])
        self.assertEqual([event["username"] for event in data["events"]], ["analyst"])

    def test_audit_can_be_sorted_by_each_table_column(self):
        cases = [
            ("created", "asc", "admin"),
            ("username", "desc", "analyst"),
            ("action_type", "asc", "analyst"),
            ("info", "desc", "admin"),
        ]

        for sort, direction, expected_username in cases:
            with self.subTest(sort=sort, direction=direction):
                response = self.client.get(reverse("audit_events"), {"sort": sort, "direction": direction})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["events"][0]["username"], expected_username)

    def test_analyst_only_sees_own_users_in_audit_filter(self):
        session = self.client.session
        session[SESSION_USER_ID_KEY] = self.analyst.pk
        session.save()

        data = self.client.get(reverse("audit_events")).json()

        self.assertEqual(data["users"], ["analyst"])
        self.assertEqual([event["username"] for event in data["events"]], ["analyst"])
