from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("db_statistics", "0002_ensure_favorite_table"),
    ]

    operations = [
        migrations.RenameModel(
            old_name="Favorite",
            new_name="DBFavorite",
        ),
        migrations.RenameModel(
            old_name="UserSidebarSettings",
            new_name="DBUserSidebarSettings",
        ),
        migrations.AlterField(
            model_name="dbfavorite",
            name="connection",
            field=models.ForeignKey(
                db_comment="Подключение",
                on_delete=django.db.models.deletion.CASCADE,
                related_name="connection_db_favorite",
                to="db_statistics.dbconnection",
                verbose_name="Подключение",
            ),
        ),
        migrations.AlterField(
            model_name="dbfavorite",
            name="user",
            field=models.ForeignKey(
                db_comment="Пользователь",
                on_delete=django.db.models.deletion.CASCADE,
                related_name="user_db_favorite",
                to="db_statistics.dbuser",
                verbose_name="Пользователь",
            ),
        ),
        migrations.AlterField(
            model_name="dbusersidebarsettings",
            name="user",
            field=models.OneToOneField(
                db_comment="Пользователь",
                on_delete=django.db.models.deletion.CASCADE,
                related_name="user_db_user_sidebar_settings",
                to="db_statistics.dbuser",
                verbose_name="Пользователь",
            ),
        ),
    ]
