import json
from types import SimpleNamespace
from unittest.mock import patch

from django.test import RequestFactory, SimpleTestCase

from db_statistics import views


class AnalystDestructiveActionsTests(SimpleTestCase):
    def setUp(self):
        self.analyst = SimpleNamespace(pk=1, login="analyst", email="analyst@example.com", role="Аналитик")
        self.request = RequestFactory().post(
            "/",
            data=json.dumps({}),
            content_type="application/json",
        )

    def test_destructive_api_endpoints_are_forbidden(self):
        endpoints = (
            views.terminate_active_query,
            views.terminate_active_session,
            views.maintenance_vacuum,
        )

        with patch.object(views, "_current_db_user", return_value=self.analyst):
            for endpoint in endpoints:
                with self.subTest(endpoint=endpoint.__name__):
                    response = endpoint(self.request)
                    self.assertEqual(response.status_code, 403)
                    self.assertFalse(json.loads(response.content)["ok"])

    def test_anonymous_user_receives_unauthorized_response(self):
        with patch.object(views, "_current_db_user", return_value=None):
            response = views.terminate_active_query(self.request)

        self.assertEqual(response.status_code, 401)

    def test_analyst_payload_disables_destructive_actions(self):
        with patch.object(views, "_sidebar_settings_for_user") as settings_for_user:
            settings_for_user.return_value.visible_tabs = None
            payload = views._user_payload(self.analyst)

        self.assertFalse(payload["can_run_destructive_actions"])
        self.assertNotIn("audit", payload["sidebar_visible_tabs"])

    def test_audit_api_is_forbidden_for_analyst(self):
        request = RequestFactory().get("/audit/events/")
        with patch.object(views, "_current_db_user", return_value=self.analyst):
            response = views.audit_events(request)

        self.assertEqual(response.status_code, 403)
        self.assertFalse(json.loads(response.content)["ok"])

    def test_sidebar_settings_exclude_audit_for_analyst(self):
        settings = SimpleNamespace(visible_tabs=None)
        request = RequestFactory().get("/settings/sidebar/")
        with (
            patch.object(views, "_current_db_user", return_value=self.analyst),
            patch.object(views, "_sidebar_settings_for_user", return_value=settings),
        ):
            response = views.sidebar_settings(request)

        payload = json.loads(response.content)
        self.assertNotIn("audit", payload["available_tabs"])
        self.assertNotIn("audit", payload["visible_tabs"])
