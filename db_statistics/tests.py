from django.test import SimpleTestCase

from db_statistics.views import SESSION_EXPIRES_AT_KEY, SIDEBAR_TAB_IDS, _normalize_sidebar_tabs, _session_duration_seconds, _session_has_expired


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


class SessionExpirationTests(SimpleTestCase):
    def test_detects_expired_session(self):
        self.assertTrue(_session_has_expired({SESSION_EXPIRES_AT_KEY: 100}, now_timestamp=100))
        self.assertTrue(_session_has_expired({SESSION_EXPIRES_AT_KEY: 99}, now_timestamp=100))

    def test_keeps_active_and_legacy_sessions(self):
        self.assertFalse(_session_has_expired({SESSION_EXPIRES_AT_KEY: 101}, now_timestamp=100))
        self.assertFalse(_session_has_expired({}, now_timestamp=100))

    def test_rejects_invalid_expiration_timestamp(self):
        self.assertTrue(_session_has_expired({SESSION_EXPIRES_AT_KEY: "invalid"}, now_timestamp=100))
