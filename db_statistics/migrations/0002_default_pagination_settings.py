from django.db import migrations


def create_default_pagination_settings(apps, schema_editor):
    pagination_settings = apps.get_model("db_statistics", "DBPaginationSettings")
    pagination_settings.objects.bulk_create(
        [pagination_settings(size=20), pagination_settings(size=50)],
        ignore_conflicts=True,
    )


def remove_default_pagination_settings(apps, schema_editor):
    pagination_settings = apps.get_model("db_statistics", "DBPaginationSettings")
    pagination_settings.objects.filter(size__in=(20, 50)).delete()


class Migration(migrations.Migration):
    dependencies = [("db_statistics", "0001_initial")]

    operations = [
        migrations.RunPython(
            create_default_pagination_settings,
            remove_default_pagination_settings,
        ),
        migrations.RunSQL(
            sql="""
                CREATE TRIGGER db_pagination_settings_max_rows
                BEFORE INSERT ON db_pagination_settings
                WHEN (SELECT COUNT(*) FROM db_pagination_settings) >= 5
                BEGIN
                    SELECT RAISE(ABORT, 'Maximum of 5 pagination settings exceeded');
                END;
            """,
            reverse_sql="DROP TRIGGER IF EXISTS db_pagination_settings_max_rows;",
        ),
    ]
