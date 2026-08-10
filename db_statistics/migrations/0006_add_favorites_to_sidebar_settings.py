from django.db import migrations


def add_favorites_tab(apps, schema_editor):
    sidebar_settings = apps.get_model("db_statistics", "DBUserSidebarSettings")
    for settings in sidebar_settings.objects.all().iterator():
        visible_tabs = list(settings.visible_tabs or [])
        if "favorites" not in visible_tabs:
            visible_tabs.append("favorites")
            settings.visible_tabs = visible_tabs
            settings.save(update_fields=["visible_tabs"])


def remove_favorites_tab(apps, schema_editor):
    sidebar_settings = apps.get_model("db_statistics", "DBUserSidebarSettings")
    for settings in sidebar_settings.objects.all().iterator():
        visible_tabs = [tab for tab in (settings.visible_tabs or []) if tab != "favorites"]
        settings.visible_tabs = visible_tabs
        settings.save(update_fields=["visible_tabs"])


class Migration(migrations.Migration):
    dependencies = [("db_statistics", "0005_alter_dbaudit_action_type")]

    operations = [migrations.RunPython(add_favorites_tab, remove_favorites_tab)]
