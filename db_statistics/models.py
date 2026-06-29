import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models


ENCRYPTED_PASSWORD_PREFIX = "enc$"


def _connection_password_cipher():
    secret = getattr(settings, "DB_CONNECTION_ENCRYPTION_KEY", "") or settings.SECRET_KEY
    key = base64.urlsafe_b64encode(hashlib.sha256(str(secret).encode("utf-8")).digest())
    return Fernet(key)


def encrypt_connection_password(raw_password):
    if raw_password in (None, ""):
        return raw_password or ""
    text = str(raw_password)
    if text.startswith(ENCRYPTED_PASSWORD_PREFIX):
        return text
    token = _connection_password_cipher().encrypt(text.encode("utf-8")).decode("utf-8")
    return f"{ENCRYPTED_PASSWORD_PREFIX}{token}"


def decrypt_connection_password(stored_password):
    if stored_password in (None, ""):
        return stored_password or ""
    text = str(stored_password)
    if not text.startswith(ENCRYPTED_PASSWORD_PREFIX):
        return text
    token = text[len(ENCRYPTED_PASSWORD_PREFIX):]
    try:
        return _connection_password_cipher().decrypt(token.encode("utf-8")).decode("utf-8")
    except InvalidToken:
        return ""


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
        ordering = ['login', ]

    def __str__(self):
        return self.login


class DBConnection(DateStamp, Active):
    """Подключение"""
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
        db_table_comment = "Подключение"
        verbose_name = "Подключение"
        verbose_name_plural = "Подключения"
        unique_together = ("name", "host", "port", "database")

    def set_password(self, raw_password):
        self.password = encrypt_connection_password(raw_password)

    def get_password(self):
        decrypted_password = decrypt_connection_password(self.password)
        if self.password and not str(self.password).startswith(ENCRYPTED_PASSWORD_PREFIX) and self.pk:
            encrypted_password = encrypt_connection_password(self.password)
            type(self).objects.filter(pk=self.pk).update(password=encrypted_password)
            self.password = encrypted_password
        return decrypted_password

    def save(self, *args, **kwargs):
        self.password = encrypt_connection_password(self.password)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class DBAudit(models.Model):
    """Аудит"""
    ACTION_TYPES = [
        ('create', 'Создание'),
        ('update', 'Обновление'),
        ('delete', 'Удаление'),
        ('register', 'Регистрация'),
        ('download', 'Скачивание'),
        ('info', 'Информация'),
    ]

    username = models.CharField(verbose_name="Пользователь", db_comment="Пользователь", max_length=200)
    action_type = models.CharField(verbose_name="Действие", db_comment="Действие", max_length=10, choices=ACTION_TYPES)
    info = models.TextField(verbose_name="Информация", db_comment="Информация")
    created = models.DateTimeField(verbose_name="Дата действия", db_comment="Дата действия")

    def __str__(self):
        return f"{self.username} - {self.action_type}"

    class Meta:
        db_table = "db_audit"
        db_table_comment = "Аудит"
        verbose_name = "Аудит"
        verbose_name_plural = "Аудит"
        ordering = ("-created",)


class DBPagination(DateStamp):
    """Пагинация"""
    pagination_size = models.IntegerField(verbose_name="Размер пагинации", db_comment="Размер пагинации", default=10, validators=[MinValueValidator(10), MaxValueValidator(200)], unique=True)

    class Meta:
        db_table = "db_pagination"
        db_table_comment = "Пагинация"
        verbose_name = "Пагинация"
        verbose_name_plural = "Пагинация"
        ordering = ("pagination_size",)

    def clean(self):
        super().clean()
        if not self.pk and DBPagination.objects.count() >= 5:
            raise ValidationError("Нельзя создать больше 5 записей.")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return str(self.pagination_size)
