import json
from datetime import timedelta

from django.conf import settings
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


class LoginSessionDurationTests(TestCase):
    def setUp(self):
        self.user = DBUser.objects.create(login="analyst", email="analyst@example.com")

    def test_user_can_choose_session_duration(self):
        previous_session_key = self.client.session.session_key
        response = self.client.post(reverse("login"), {"login": self.user.login, "email": self.user.email, "session_duration": "12"})

        self.assertRedirects(response, reverse("home"))
        self.assertNotEqual(self.client.session.session_key, previous_session_key)
        self.assertEqual(self.client.session[SESSION_USER_ID_KEY], self.user.pk)
        self.assertAlmostEqual(self.client.session.get_expiry_age(), 12 * 60 * 60, delta=2)
        self.assertIn("session_duration=12h", DBAudit.objects.get(action_type="login").info)

    def test_session_duration_must_be_within_allowed_range(self):
        for duration in ("0", "25", "1.5", "invalid"):
            with self.subTest(duration=duration):
                response = self.client.post(reverse("login"), {"login": self.user.login, "email": self.user.email, "session_duration": duration})

                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "Время сессии должно быть от 1 до 24 часов")
                self.assertNotIn(SESSION_USER_ID_KEY, self.client.session)

    def test_session_duration_defaults_to_eight_hours(self):
        response = self.client.post(reverse("login"), {"login": self.user.login, "email": self.user.email})

        self.assertRedirects(response, reverse("home"))
        self.assertAlmostEqual(self.client.session.get_expiry_age(), 8 * 60 * 60, delta=2)


class SidebarFavoritesSettingsTests(TestCase):
    def setUp(self):
        self.user = DBUser.objects.create(login="analyst", email="analyst@example.com")
        session = self.client.session
        session[SESSION_USER_ID_KEY] = self.user.pk
        session.save()

    def test_favorites_is_available_in_sidebar_settings(self):
        data = self.client.get(reverse("sidebar_settings")).json()

        self.assertIn("favorites", data["available_tabs"])
        self.assertIn("favorites", data["visible_tabs"])

    def test_user_can_hide_favorites_in_sidebar_settings(self):
        response = self.client.post(reverse("sidebar_settings"), data=json.dumps({"visible_tabs": ["tables", "audit"]}), content_type="application/json")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["visible_tabs"], ["tables", "audit"])

    def test_favorites_filters_are_rendered_in_english(self):
        self.client.cookies[settings.LANGUAGE_COOKIE_NAME] = "en"

        response = self.client.get(reverse("home"))

        self.assertContains(response, '<option value="">All records</option>', count=5, html=True)
        self.assertContains(response, '<option value="favorites">Favorites only</option>', count=5, html=True)


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
