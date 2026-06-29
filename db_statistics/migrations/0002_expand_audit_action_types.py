from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("db_statistics", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="dbaudit",
            name="action_type",
            field=models.CharField(
                choices=[
                    ("login", "Вход"),
                    ("connection_create", "Создание подключения"),
                    ("connection_update", "Изменение подключения"),
                    ("connection_delete", "Удаление подключения"),
                    ("connection_test", "Проверка подключения"),
                    ("create", "Создание"),
                    ("update", "Обновление"),
                    ("delete", "Удаление"),
                    ("register", "Регистрация"),
                    ("download", "Скачивание"),
                    ("info", "Информация"),
                ],
                db_comment="Действие",
                max_length=32,
                verbose_name="Действие",
            ),
        ),
    ]
