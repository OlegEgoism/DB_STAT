import json
from pathlib import Path

from django.test import Client, SimpleTestCase, TestCase
from django.urls import reverse

from db_statistics.models import DBUser, UserSidebarSettings
from db_statistics.views import SIDEBAR_TAB_IDS


class SidebarSettingsTemplateTests(SimpleTestCase):
    def test_sidebar_settings_controls_are_wired(self):
        sidebar = Path("templates/includes/_sidebar.html").read_text(encoding="utf-8")
        modals = Path("templates/includes/_modals.html").read_text(encoding="utf-8")
        script = Path("static/js/home.js").read_text(encoding="utf-8")

        self.assertIn('id="sidebarSettingsBtn"', sidebar)
        self.assertIn("Настройки сайдбара", sidebar)
        self.assertIn('id="sidebarSettingsModal"', modals)
        self.assertIn('id="sidebarSettingsList"', modals)
        self.assertIn("function initSidebarSettings()", script)
        self.assertIn("/settings/sidebar/", script)
        self.assertIn("currentDbUser.sidebar_visible_tabs", script)
        self.assertIn("updateSidebarForConnection();", script)
        self.assertIn("document.querySelectorAll('.nav-item[data-page]').forEach", script)

    def test_home_page_describes_settings_block(self):
        main_content = Path("templates/includes/_main_content.html").read_text(encoding="utf-8")

        self.assertIn("<strong>Настройки</strong>", main_content)
        self.assertIn("Персональная настройка бокового меню", main_content)


class SidebarSettingsModelTests(TestCase):
    def setUp(self):
        self.user = DBUser.objects.create(login="analyst", email="analyst@example.com", role="Аналитик")
        self.client = Client(enforce_csrf_checks=False)
        session = self.client.session
        session["db_user_id"] = self.user.pk
        session.save()

    def test_sidebar_settings_endpoint_persists_visible_tabs_for_user(self):
        response = self.client.post(reverse("sidebar_settings"), data=json.dumps({"visible_tabs": ["tables", "audit", "unknown"]}), content_type="application/json")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["visible_tabs"], ["tables", "audit"])
        self.assertEqual(UserSidebarSettings.objects.get(user=self.user).visible_tabs, ["tables", "audit"])

    def test_sidebar_settings_endpoint_defaults_to_all_tabs_when_payload_is_empty(self):
        response = self.client.post(reverse("sidebar_settings"), data=json.dumps({"visible_tabs": []}), content_type="application/json")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["visible_tabs"], SIDEBAR_TAB_IDS)
