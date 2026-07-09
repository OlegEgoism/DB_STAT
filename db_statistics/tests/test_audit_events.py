from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from db_statistics.models import DBAudit, DBUser


class AuditEventsTests(TestCase):
    def setUp(self):
        self.user = DBUser.objects.create(login="analyst", email="analyst@example.com", role="Аналитик")
        self.client = Client(enforce_csrf_checks=False)
        session = self.client.session
        session["db_user_id"] = self.user.pk
        session.save()
        DBAudit.objects.create(username="analyst", action_type="login", info="login", created=timezone.now())
        DBAudit.objects.create(username="analyst", action_type="logout", info="logout", created=timezone.now())
        DBAudit.objects.create(username="analyst", action_type="connection_test", info="test", created=timezone.now())
        DBAudit.objects.create(username="other", action_type="login", info="other", created=timezone.now())

    def test_audit_events_filters_by_multiple_selected_actions(self):
        response = self.client.get(reverse("audit_events"), data={"action_types": ["login", "connection_test"]})

        self.assertEqual(response.status_code, 200)
        action_types = {event["action_type"] for event in response.json()["events"]}
        self.assertEqual(action_types, {"login", "connection_test"})
        self.assertEqual(response.json()["total_count"], 2)

    def test_audit_events_keeps_legacy_single_action_filter(self):
        response = self.client.get(reverse("audit_events"), data={"action_type": "logout"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual([event["action_type"] for event in response.json()["events"]], ["logout"])

    def test_audit_events_rejects_unknown_selected_action(self):
        response = self.client.get(reverse("audit_events"), data={"action_types": ["login", "unknown"]})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["message"], "Неизвестный тип действия")
