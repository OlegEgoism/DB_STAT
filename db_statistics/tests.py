from django.test import TestCase, override_settings


class PageNotFoundTests(TestCase):
    def assert_project_404(self):
        response = self.client.get("/missing-page/")

        self.assertEqual(response.status_code, 404)
        self.assertTemplateUsed(response, "404.html")
        self.assertContains(response, "Transaction Rollback", status_code=404)
        self.assertContains(response, "'/missing-page/'", status_code=404)
        self.assertContains(response, "ABORTED", status_code=404)
        self.assertContains(response, 'href="/"', status_code=404)

    def test_unknown_url_uses_project_404_page_in_debug_mode(self):
        self.assert_project_404()

    @override_settings(DEBUG=False)
    def test_unknown_url_uses_project_404_page_in_production_mode(self):
        self.assert_project_404()
