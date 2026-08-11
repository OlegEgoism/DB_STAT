from django.test import SimpleTestCase

from db_statistics.views import SIDEBAR_TAB_IDS, _normalize_sidebar_tabs


class SidebarTabNormalizationTests(SimpleTestCase):
    def test_preserves_custom_order_and_removes_duplicates(self):
        tabs = ["tables", "databases", "tables", "audit"]

        self.assertEqual(_normalize_sidebar_tabs(tabs), ["tables", "databases", "audit"])

    def test_ignores_unknown_tabs(self):
        self.assertEqual(_normalize_sidebar_tabs(["tables", "unknown", "users"]), ["tables", "users"])

    def test_uses_default_order_when_selection_is_empty(self):
        self.assertEqual(_normalize_sidebar_tabs([]), SIDEBAR_TAB_IDS)
