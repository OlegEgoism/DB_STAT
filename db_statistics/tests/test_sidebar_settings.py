from pathlib import Path

from django.test import SimpleTestCase


class SidebarSettingsTests(SimpleTestCase):
    def test_sidebar_settings_controls_are_wired(self):
        main_content = Path("templates/includes/_main_content.html").read_text(encoding="utf-8")
        modals = Path("templates/includes/_modals.html").read_text(encoding="utf-8")
        script = Path("static/js/home.js").read_text(encoding="utf-8")

        self.assertIn('id="sidebarSettingsBtn"', main_content)
        self.assertIn('id="sidebarSettingsModal"', modals)
        self.assertIn('id="sidebarSettingsList"', modals)
        self.assertIn("function initSidebarSettings()", script)
        self.assertIn("dbstat_sidebar_visible_tabs_", script)
        self.assertIn("updateSidebarForConnection();", script)
