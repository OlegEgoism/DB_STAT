import json

from django.conf import settings
from django.template.loader import render_to_string
from django.test import Client, SimpleTestCase, TestCase
from django.urls import reverse
from django.utils import translation


class LanguageSettingsTests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_english_language_is_saved_in_session_and_cookie(self):
        response = self.client.post(reverse("language_settings"), data=json.dumps({"language": "en"}), content_type="application/json")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"ok": True, "language": "en"})
        self.assertEqual(self.client.session["django_language"], "en")
        self.assertEqual(response.cookies[settings.LANGUAGE_COOKIE_NAME].value, "en")

    def test_only_ru_and_en_are_accepted(self):
        response = self.client.post(reverse("language_settings"), data=json.dumps({"language": "de"}), content_type="application/json")

        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()["ok"])

    def test_language_endpoint_requires_post(self):
        response = self.client.get(reverse("language_settings"))

        self.assertEqual(response.status_code, 405)


class EnglishSearchFieldsTests(SimpleTestCase):
    def test_dashboard_search_and_filter_placeholders_are_rendered_in_english(self):
        with translation.override("en"):
            content = render_to_string("includes/_main_content.html")

        self.assertIn('placeholder="Search by schema..."', content)
        self.assertIn('placeholder="Search by schema or table..."', content)
        self.assertIn('placeholder="Search by schema or view..."', content)
        self.assertIn('placeholder="Search by user..."', content)
        self.assertIn('placeholder="Search by group..."', content)
        self.assertIn('placeholder="All users"', content)
        self.assertIn('<option value="">All types</option>', content)
        self.assertIn('<option value="ordinary">Regular</option>', content)
        self.assertIn('<option value="materialized">Materialized</option>', content)
        self.assertIn('<option value="active">Active</option>', content)
        self.assertIn('<option value="idle">Idle</option>', content)
        self.assertIn('<option value="idle in transaction">Idle in transaction</option>', content)
        self.assertIn('<option value="0">Manual</option>', content)
        self.assertIn('<span>Blocked user</span>', content)
        self.assertIn('<span>Blocking user</span>', content)
        self.assertIn('aria-label="Audit action filter"', content)
        self.assertIn('<option value="">All actions</option>', content)
        self.assertNotIn('placeholder="Поиск ', content)
        self.assertNotIn('placeholder="Все пользователи"', content)
        self.assertNotIn('<option value="0">Вручную</option>', content)
        self.assertNotIn('<span>Обновление</span>', content)
