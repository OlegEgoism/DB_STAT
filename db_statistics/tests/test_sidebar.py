from types import SimpleNamespace

from django.conf import settings
from django.test import SimpleTestCase

from db_statistics.views.helpers import _sidebar_settings_values


def _settings_with(value):
    return SimpleNamespace(visible_tabs=value)


class SidebarNewTabTests(SimpleTestCase):
    NEW_TAB = "toast-tables"

    def test_legacy_list_without_known_tabs_gets_new_tab_after_its_neighbour(self):
        stored = [tab for tab in settings.SIDEBAR_TAB_IDS if tab != self.NEW_TAB]

        visible, _sections = _sidebar_settings_values(_settings_with(stored))

        self.assertIn(self.NEW_TAB, visible)
        self.assertEqual(visible[visible.index("temp-tables") + 1], self.NEW_TAB)

    def test_tab_hidden_by_user_stays_hidden_when_it_was_already_known(self):
        stored = {"visible_tabs": [tab for tab in settings.SIDEBAR_TAB_IDS if tab != self.NEW_TAB], "section_order": settings.SIDEBAR_SECTION_IDS.copy(), "known_tabs": settings.SIDEBAR_TAB_IDS.copy()}

        visible, _sections = _sidebar_settings_values(_settings_with(stored))

        self.assertNotIn(self.NEW_TAB, visible)

    def test_tab_missing_from_known_tabs_is_added_for_dict_settings(self):
        stored = {"visible_tabs": [tab for tab in settings.SIDEBAR_TAB_IDS if tab != self.NEW_TAB], "section_order": settings.SIDEBAR_SECTION_IDS.copy(), "known_tabs": [tab for tab in settings.SIDEBAR_TAB_IDS if tab != self.NEW_TAB]}

        visible, _sections = _sidebar_settings_values(_settings_with(stored))

        self.assertIn(self.NEW_TAB, visible)

    def test_fixed_tabs_are_always_present(self):
        visible, _sections = _sidebar_settings_values(_settings_with({"visible_tabs": ["tables"], "section_order": [], "known_tabs": settings.SIDEBAR_TAB_IDS.copy()}))

        for fixed in settings.FIXED_SIDEBAR_TAB_IDS:
            self.assertIn(fixed, visible)
