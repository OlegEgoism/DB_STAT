from django.contrib.admin.sites import AdminSite
from django.test import SimpleTestCase

from db_statistics.admin import UserSidebarSettingsAdmin
from db_statistics.models import DBUser, UserSidebarSettings


class UserSidebarSettingsAdminTests(SimpleTestCase):
    def test_visible_tabs_display_uses_russian_labels(self):
        admin = UserSidebarSettingsAdmin(UserSidebarSettings, AdminSite())
        settings = UserSidebarSettings(user=DBUser(login="analyst"), visible_tabs=["database-overview", "temp-tables", "audit"])

        self.assertEqual(admin.visible_tabs_display(settings), "База данных, Временные таблицы, Аудит")

    def test_visible_tabs_display_defaults_to_all_tabs_text(self):
        admin = UserSidebarSettingsAdmin(UserSidebarSettings, AdminSite())
        settings = UserSidebarSettings(user=DBUser(login="analyst"), visible_tabs=[])

        self.assertEqual(admin.visible_tabs_display(settings), "Все вкладки")
