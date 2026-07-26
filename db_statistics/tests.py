from types import SimpleNamespace

from django.template.loader import render_to_string
from django.test import SimpleTestCase, TestCase, override_settings


class DashboardVisualStatusTests(SimpleTestCase):
    def test_dashboard_contains_accessible_connection_health_summary(self):
        html = render_to_string("home.html", {"db_user": SimpleNamespace(login="operator", email="operator@example.com", role="Оператор"), "db_user_json": "{}", "user_can_manage_connections": False})

        self.assertIn('id="connectionHealth"', html)
        self.assertIn('aria-live="polite"', html)
        self.assertIn('id="connectionHealthConnections"', html)
        self.assertIn('id="connectionHealthCache"', html)
        self.assertIn('id="connectionHealthRollback"', html)


class PageNotFoundTests(TestCase):
    def assert_project_404(self):
        response = self.client.get("/missing-page/")

        self.assertEqual(response.status_code, 404)
        self.assertTemplateUsed(response, "404.html")
        self.assertContains(response, "Страница не найдена | DB STAT", status_code=404)
        self.assertContains(response, "/missing-page/", status_code=404)
        self.assertContains(response, "ABORTED", status_code=404)
        self.assertContains(response, 'href="/"', status_code=404)

    def test_unknown_url_uses_project_404_page_in_debug_mode(self):
        self.assert_project_404()

    @override_settings(DEBUG=False)
    def test_unknown_url_uses_project_404_page_in_production_mode(self):
        self.assert_project_404()
