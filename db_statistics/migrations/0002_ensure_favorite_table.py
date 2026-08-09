from django.db import migrations


def ensure_favorite_table(apps, schema_editor):
    """Восстанавливает таблицу избранного, если 0001 ранее отметили применённой без неё."""
    favorite = apps.get_model("db_statistics", "Favorite")
    existing_tables = schema_editor.connection.introspection.table_names()
    if favorite._meta.db_table not in existing_tables:
        schema_editor.create_model(favorite)


def drop_favorite_table(apps, schema_editor):
    favorite = apps.get_model("db_statistics", "Favorite")
    if favorite._meta.db_table in schema_editor.connection.introspection.table_names():
        schema_editor.delete_model(favorite)


class Migration(migrations.Migration):
    dependencies = [("db_statistics", "0001_initial")]
    operations = [migrations.RunPython(ensure_favorite_table, drop_favorite_table)]
