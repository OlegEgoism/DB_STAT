from operator import truediv

from django.db import models


# ============================================================================
# АБСТРАКЦИИ
# ============================================================================
class DateStamp(models.Model):
    """Временные отметки"""

    created = models.DateTimeField(verbose_name="Дата создания", db_comment="Дата создания", auto_now_add=True)
    updated = models.DateTimeField(verbose_name="Дата изменения", db_comment="Дата изменения", auto_now=True)

    class Meta:
        abstract = True


class Active(models.Model):
    """Статус активности"""

    is_active = models.BooleanField(verbose_name="Активность", db_comment="Активность", default=True)

    class Meta:
        abstract = True


# ============================================================================
# МОДЕЛИ
# ============================================================================
class DBUser(DateStamp, Active):
    """Пользователь"""

    USER_ROLE = [
        ("Администратор", "Администратор"),
        ("Аналитик", "Аналитик")
    ]

    login = models.CharField(verbose_name="Логин", db_comment="Логин", max_length=100, db_index=True, unique=True)
    email = models.EmailField(verbose_name="Почта", db_comment="Почта", unique=True)
    role = models.CharField(verbose_name="Роль", db_comment="Роль", max_length=20, choices=USER_ROLE, default="Аналитик")
    connections = models.ManyToManyField(to="db_statistics.DBConnection", verbose_name="Подключение к базе данных", db_comment="Подключение к базе данных", blank=True)

    class Meta:
        db_table = "db_user"
        db_table_comment = "Пользователь"
        verbose_name = "Пользователь"
        verbose_name_plural = "Пользователи"

    def __str__(self):
        return self.login


class DBConnection(DateStamp, Active):
    """Подключение к базе данных"""
    DATABASE_TYPES = [
        ("PostgreSQL", "PostgreSQL"),
        ("Greenplum", "Greenplum")
    ]

    name = models.CharField(verbose_name="Название", db_comment="Название", max_length=120)
    host = models.CharField(verbose_name="Хост", db_comment="Хост", max_length=255)
    port = models.PositiveIntegerField(verbose_name="Порт", db_comment="Порт", default=5432)
    database = models.CharField(verbose_name="База данных", db_comment="База данных", max_length=120)
    username = models.CharField(verbose_name="Пользователь", db_comment="Пользователь", max_length=120)
    password = models.CharField(verbose_name="Пароль", db_comment="Пароль", max_length=255)
    db_type = models.CharField(verbose_name="Тип базы данных", db_comment="Тип базы данных", max_length=20, choices=DATABASE_TYPES, default="PostgreSQL")

    class Meta:
        db_table = "db_connection"
        db_table_comment = "Подключение к базе данных"
        verbose_name = "Подключение к базе данных"
        verbose_name_plural = "Подключения к базам данных"
        unique_together = ("name", "host", "port", "database")

    def __str__(self):
        return self.name
