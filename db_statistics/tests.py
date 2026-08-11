from django.test import SimpleTestCase

from db_statistics.views import SIDEBAR_TAB_IDS, _normalize_sidebar_tabs, _session_duration_seconds


class SidebarTabNormalizationTests(SimpleTestCase):
    def test_preserves_custom_order_and_removes_duplicates(self):
        tabs = ["tables", "databases", "tables", "audit"]

        self.assertEqual(_normalize_sidebar_tabs(tabs), ["tables", "databases", "audit"])

    def test_ignores_unknown_tabs(self):
        self.assertEqual(_normalize_sidebar_tabs(["tables", "unknown", "users"]), ["tables", "users"])

    def test_uses_default_order_when_selection_is_empty(self):
        self.assertEqual(_normalize_sidebar_tabs([]), SIDEBAR_TAB_IDS)


class SessionDurationTests(SimpleTestCase):
    def test_accepts_duration_from_ten_minutes_to_twenty_four_hours(self):
        self.assertEqual(_session_duration_seconds("0.1667"), 600)
        self.assertEqual(_session_duration_seconds("0.5"), 1800)
        self.assertEqual(_session_duration_seconds("24"), 86400)

    def test_rejects_duration_outside_limits(self):
        self.assertIsNone(_session_duration_seconds("0.16"))
        self.assertIsNone(_session_duration_seconds("24.01"))

    def test_rejects_non_numeric_duration(self):
        self.assertIsNone(_session_duration_seconds("invalid"))
