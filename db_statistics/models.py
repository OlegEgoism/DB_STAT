from django.db import models


class DatabaseConnection(models.Model):
    DATABASE_TYPES = [("postgresql", "PostgreSQL"), ("greenplum", "Greenplum")]

    name = models.CharField("Название", max_length=120)
    db_type = models.CharField("Тип БД", max_length=20, choices=DATABASE_TYPES, default="postgresql")
    host = models.CharField("Хост", max_length=255)
    port = models.PositiveIntegerField("Порт", default=5432)
    database = models.CharField("База данных", max_length=120)
    username = models.CharField("Пользователь", max_length=120)
    password = models.CharField("Пароль", max_length=255)
    created_at = models.DateTimeField("Создано", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлено", auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Подключение к БД"
        verbose_name_plural = "Подключения к БД"

    def __str__(self):
        return f"{self.name} ({self.host}:{self.port}/{self.database})"
