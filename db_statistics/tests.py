from django.test import TestCase, override_settings


class PageNotFoundTests(TestCase):
    @override_settings(DEBUG=False)
    def test_unknown_url_uses_project_404_page(self):
        response = self.client.get("/missing-page/")

        self.assertEqual(response.status_code, 404)
        self.assertTemplateUsed(response, "404.html")
        self.assertContains(response, "Страница не найдена", status_code=404)
        self.assertContains(response, 'href="/"', status_code=404)
