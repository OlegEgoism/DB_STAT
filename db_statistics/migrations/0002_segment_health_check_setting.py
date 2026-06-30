from django.db import migrations, models
import django.db.models.deletion


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
                    ("segment_health_check", "Фоновая проверка сегментов"),
                ],
                db_comment="Действие",
                max_length=32,
                verbose_name="Действие",
            ),
        ),
        migrations.CreateModel(
            name="DBSegmentHealthCheckSetting",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created", models.DateTimeField(auto_now_add=True, db_comment="Дата создания", verbose_name="Дата создания")),
                ("updated", models.DateTimeField(auto_now=True, db_comment="Дата изменения", verbose_name="Дата изменения")),
                ("is_active", models.BooleanField(db_comment="Активность", default=True, verbose_name="Активность")),
                ("interval_minutes", models.PositiveIntegerField(db_comment="Период выполнения фонового запроса Состояние сегментов в минутах", default=60, verbose_name="Период выполнения, минут")),
                ("last_run_at", models.DateTimeField(blank=True, db_comment="Дата последнего запуска", null=True, verbose_name="Дата последнего запуска")),
                ("next_run_at", models.DateTimeField(blank=True, db_comment="Дата следующего запуска", null=True, verbose_name="Дата следующего запуска")),
                ("connection", models.OneToOneField(db_comment="Подключение", on_delete=django.db.models.deletion.CASCADE, related_name="segment_health_check_setting", to="db_statistics.dbconnection", verbose_name="Подключение")),
            ],
            options={
                "verbose_name": "Настройка проверки сегментов",
                "verbose_name_plural": "Настройки проверки сегментов",
                "db_table": "db_segment_health_check_setting",
                "db_table_comment": "Настройки фоновой проверки сегментов",
                "ordering": ("connection__name",),
            },
        ),
    ]
