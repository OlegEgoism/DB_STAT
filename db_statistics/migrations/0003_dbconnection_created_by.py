# Generated manually to add connection ownership metadata.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("db_statistics", "0002_expand_audit_action_types"),
    ]

    operations = [
        migrations.AddField(
            model_name="dbconnection",
            name="created_by",
            field=models.ForeignKey(
                blank=True,
                db_comment="Пользователь, создавший подключение",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="created_connections",
                to="db_statistics.dbuser",
                verbose_name="Создал пользователь",
            ),
        ),
    ]
