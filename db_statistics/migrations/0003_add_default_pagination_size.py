from django.db import migrations


def add_default_pagination_size(apps, schema_editor):
    pagination_settings = apps.get_model("db_statistics", "DBPaginationSettings")
    pagination_settings.objects.get_or_create(size=10)


def remove_default_pagination_size(apps, schema_editor):
    pagination_settings = apps.get_model("db_statistics", "DBPaginationSettings")
    pagination_settings.objects.filter(size=10).delete()


class Migration(migrations.Migration):
    dependencies = [("db_statistics", "0002_default_pagination_settings")]

    operations = [
        migrations.RunPython(
            add_default_pagination_size,
            remove_default_pagination_size,
        )
    ]
