import json

from django.conf import settings
from django.test import Client, TestCase
from django.urls import reverse


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
