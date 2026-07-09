from pathlib import Path

from django.test import SimpleTestCase


class LogoutCsrfTemplateTests(SimpleTestCase):
    def test_logout_form_can_refresh_csrf_token_before_submit(self):
        template = Path("templates/includes/_main_content.html").read_text(encoding="utf-8")
        script = Path("static/js/home.js").read_text(encoding="utf-8")

        self.assertIn('id="logoutForm"', template)
        self.assertIn("{% csrf_token %}", template)
        self.assertIn("function initLogoutForm()", script)
        self.assertIn("initLogoutForm();", script)
        self.assertIn("csrfInput.value = csrfToken;", script)
