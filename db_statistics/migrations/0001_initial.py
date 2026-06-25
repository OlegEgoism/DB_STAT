# Generated manually to persist the existing monitoring models.

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="DBConnection",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created", models.DateTimeField(auto_now_add=True, db_comment="Дата создания", verbose_name="Дата создания")),
                ("updated", models.DateTimeField(auto_now=True, db_comment="Дата изменения", verbose_name="Дата изменения")),
                ("is_active", models.BooleanField(db_comment="Активность", default=True, verbose_name="Активность")),
                ("name", models.CharField(db_comment="Название", max_length=120, verbose_name="Название")),
                ("host", models.CharField(db_comment="Хост", max_length=255, verbose_name="Хост")),
                ("port", models.PositiveIntegerField(db_comment="Порт", default=5432, verbose_name="Порт")),
                ("database", models.CharField(db_comment="База данных", max_length=120, verbose_name="База данных")),
                ("username", models.CharField(db_comment="Пользователь", max_length=120, verbose_name="Пользователь")),
                ("password", models.CharField(db_comment="Пароль", max_length=255, verbose_name="Пароль")),
                ("db_type", models.CharField(choices=[("PostgreSQL", "PostgreSQL"), ("Greenplum", "Greenplum")], db_comment="Тип базы данных", default="PostgreSQL", max_length=20, verbose_name="Тип базы данных")),
            ],
            options={
                "verbose_name": "Подключение",
                "verbose_name_plural": "Подключения",
                "db_table": "db_connection",
                "db_table_comment": "Подключение",
                "unique_together": {("name", "host", "port", "database")},
            },
        ),
        migrations.CreateModel(
            name="DBAudit",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("username", models.CharField(db_comment="Пользователь", max_length=200, verbose_name="Пользователь")),
                ("action_type", models.CharField(choices=[("create", "Создание"), ("update", "Обновление"), ("delete", "Удаление"), ("register", "Регистрация"), ("download", "Скачивание"), ("info", "Информация")], db_comment="Действие", max_length=10, verbose_name="Действие")),
                ("info", models.TextField(db_comment="Информация", verbose_name="Информация")),
                ("created", models.DateTimeField(db_comment="Дата действия", verbose_name="Дата действия")),
            ],
            options={
                "verbose_name": "Аудит",
                "verbose_name_plural": "Аудит",
                "db_table": "db_audit",
                "db_table_comment": "Аудит",
                "ordering": ("-created",),
            },
        ),
        migrations.CreateModel(
            name="DBPagination",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created", models.DateTimeField(auto_now_add=True, db_comment="Дата создания", verbose_name="Дата создания")),
                ("updated", models.DateTimeField(auto_now=True, db_comment="Дата изменения", verbose_name="Дата изменения")),
                ("pagination_size", models.IntegerField(db_comment="Размер пагинации", default=10, unique=True, validators=[django.core.validators.MinValueValidator(10), django.core.validators.MaxValueValidator(200)], verbose_name="Размер пагинации")),
            ],
            options={
                "verbose_name": "Пагинация",
                "verbose_name_plural": "Пагинация",
                "db_table": "db_pagination",
                "db_table_comment": "Пагинация",
                "ordering": ("pagination_size",),
            },
        ),
        migrations.CreateModel(
            name="DBUser",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created", models.DateTimeField(auto_now_add=True, db_comment="Дата создания", verbose_name="Дата создания")),
                ("updated", models.DateTimeField(auto_now=True, db_comment="Дата изменения", verbose_name="Дата изменения")),
                ("is_active", models.BooleanField(db_comment="Активность", default=True, verbose_name="Активность")),
                ("login", models.CharField(db_comment="Логин", db_index=True, max_length=100, unique=True, verbose_name="Логин")),
                ("email", models.EmailField(db_comment="Почта", max_length=254, unique=True, verbose_name="Почта")),
                ("role", models.CharField(choices=[("Администратор", "Администратор"), ("Аналитик", "Аналитик")], db_comment="Роль", default="Аналитик", max_length=20, verbose_name="Роль")),
                ("connections", models.ManyToManyField(blank=True, db_comment="Подключение к базе данных", to="db_statistics.dbconnection", verbose_name="Подключение к базе данных")),
            ],
            options={
                "verbose_name": "Пользователь",
                "verbose_name_plural": "Пользователи",
                "db_table": "db_user",
                "db_table_comment": "Пользователь",
                "ordering": ["login"],
            },
        ),
    ]
