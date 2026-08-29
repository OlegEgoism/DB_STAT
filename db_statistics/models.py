import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.db import models

ENCRYPTED_PASSWORD_PREFIX = "enc$"


def vn(name: str, **kwargs) -> dict:
    """Возвращает общее отображаемое имя поля для интерфейса Django."""
    return {"verbose_name": name, **kwargs}


def _connection_password_cipher():
    """Создаёт экземпляр шифра на основе секретного ключа из настроек"""
    secret = getattr(settings, "DB_CONNECTION_ENCRYPTION_KEY", "") or settings.SECRET_KEY
    key = base64.urlsafe_b64encode(hashlib.sha256(str(secret).encode("utf-8")).digest())
    return Fernet(key)


def encrypt_connection_password(raw_password):
    """Шифрует пароль подключения"""
    if raw_password in (None, ""):
        return raw_password or ""
    text = str(raw_password)
    if text.startswith(ENCRYPTED_PASSWORD_PREFIX):
        return text
    token = _connection_password_cipher().encrypt(text.encode("utf-8")).decode("utf-8")
    return f"{ENCRYPTED_PASSWORD_PREFIX}{token}"


def decrypt_connection_password(stored_password):
    """Расшифровывает пароль подключения"""
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

    created = models.DateTimeField(**vn("Дата создания"), auto_now_add=True)
    updated = models.DateTimeField(**vn("Дата изменения"), auto_now=True)

    class Meta:
        abstract = True


class Active(models.Model):
    """Статус активности"""

    is_active = models.BooleanField(**vn("Активность"), default=True)

    class Meta:
        abstract = True


# ============================================================================
# МОДЕЛИ
# ============================================================================
class DBUser(DateStamp, Active):
    """Пользователь"""

    USER_ROLE = [("Администратор", "Администратор"), ("Аналитик", "Аналитик")]

    login = models.CharField(**vn("Логин"), max_length=100, db_index=True, unique=True)
    email = models.EmailField(**vn("Почта"), unique=True)
    role = models.CharField(**vn("Роль"), max_length=20, choices=USER_ROLE, default="Аналитик")
    connections = models.ManyToManyField(to="db_statistics.DBConnection", verbose_name="Подключение к базе данных", blank=True)

    class Meta:
        db_table = "db_user"
        verbose_name = "Пользователь"
        verbose_name_plural = "Пользователи"
        ordering = ["login"]

    def __str__(self):
        return self.login


class DBUserSidebarSettings(DateStamp):
    """Настройки сайдбара """

    user = models.OneToOneField(to="db_statistics.DBUser", **vn("Пользователь"), related_name="user_db_user_sidebar_settings", on_delete=models.CASCADE)
    visible_tabs = models.JSONField(**vn("Видимые вкладки"), default=list, blank=True)

    class Meta:
        db_table = "db_user_sidebar_settings"
        verbose_name = "Настройки сайдбара"
        verbose_name_plural = "Настройки сайдбара"

    def __str__(self):
        return f"Настройки сайдбара: {self.user.login}"


class DBFavorite(DateStamp):
    """Избранные объекты"""

    OBJECT_TYPES = [(value, label) for value, label in [
        ("schema", "Схема"),
        ("table", "Таблица"),
        ("view", "Представление"),
        ("function", "Функция"),
        ("user", "Пользователь"),
        ("group", "Группа")
    ]]

    user = models.ForeignKey(to="db_statistics.DBUser", **vn("Пользователь"), related_name="user_db_favorite", on_delete=models.CASCADE)
    connection = models.ForeignKey(to="db_statistics.DBConnection", **vn("Подключение"), related_name="connection_db_favorite", on_delete=models.CASCADE)
    object_type = models.CharField(**vn("Тип объекта"), max_length=16, choices=OBJECT_TYPES)
    object_key = models.CharField(**vn("Идентификатор объекта"), max_length=512)

    class Meta:
        db_table = "db_favorite"
        verbose_name = "Избранный объект"
        verbose_name_plural = "Избранные объекты"
        ordering = ("object_type", "object_key")
        constraints = [models.UniqueConstraint(fields=("user", "connection", "object_type", "object_key"), name="unique_user_connection_favorite")]

    def __str__(self):
        return f"{self.user}: {self.object_type} {self.object_key}"


class DBConnection(DateStamp, Active):
    """Подключение"""

    POSTGRESQL = "PostgreSQL"
    GREENPLUM = "Greenplum"
    GREENGAGE = "Greengage"
    DATABASE_TYPES = [(POSTGRESQL, POSTGRESQL), (GREENPLUM, GREENPLUM), (GREENGAGE, GREENGAGE)]
    GREENPLUM_COMPATIBLE_TYPES = frozenset((GREENPLUM, GREENGAGE))

    name = models.CharField(**vn("Название"), max_length=120)
    host = models.CharField(**vn("Хост"), max_length=255)
    port = models.PositiveIntegerField(**vn("Порт"), default=5432)
    database = models.CharField(**vn("База данных"), max_length=120)
    username = models.CharField(**vn("Пользователь"), max_length=120)
    password = models.CharField(**vn("Пароль"), max_length=255)
    db_type = models.CharField(**vn("Тип базы данных"), max_length=20, choices=DATABASE_TYPES, default=POSTGRESQL)
    created_user = models.ForeignKey(to="db_statistics.DBUser", **vn("Создатель подключения"), related_name="created_user_db_connection", on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        db_table = "db_connection"
        verbose_name = "Подключение"
        verbose_name_plural = "Подключения"
        unique_together = ("name", "host", "port", "database", "username")

    def get_password(self):
        """Расшифровывает пароль подключения"""
        return decrypt_connection_password(self.password)

    @property
    def is_greenplum_compatible(self):
        """Поддерживает ли СУБД функции распределённого кластера Greenplum."""
        return self.db_type in self.GREENPLUM_COMPATIBLE_TYPES

    def save(self, *args, **kwargs):
        self.password = encrypt_connection_password(self.password)
        super().save(*args, **kwargs)

    def __str__(self):
        owner = self.created_user.login if self.created_user else "не назначен"
        return f"{self.name} - (Владелец: {owner})"


class DBAudit(models.Model):
    """Аудит"""

    ACTION_TYPES = [
        ("login", "Вход"),
        ("logout", "Выход"),
        ("connection_create", "Создание подключения"),
        ("connection_update", "Изменение подключения"),
        ("connection_delete", "Удаление подключения"),
        ("connection_test", "Проверка подключения"),
        ("sidebar_settings", "Настройки сайдбара пользователя"),
        ("favorite_add", "Добавление в избранные объекты"),
        ("favorite_remove", "Удаление из избранных объектов"),
        ("query_terminate", "Завершение активного запроса"),
        ("session_terminate", "Завершение активной сессии"),
        ("vacuum", "VACUUM таблицы"),
        ("vacuum_full", "VACUUM FULL таблицы"),
        ("analyze", "ANALYZE таблицы"),
        ("explain_analyze", "EXPLAIN ANALYZE таблицы"),
    ]

    username = models.CharField(**vn("Пользователь"), max_length=200)
    action_type = models.CharField(**vn("Действие"), max_length=32, choices=ACTION_TYPES)
    info = models.TextField(**vn("Информация"))
    created = models.DateTimeField(**vn("Дата действия"))

    def __str__(self):
        return f"{self.username} - {self.action_type}"

    class Meta:
        db_table = "db_audit"
        verbose_name = "Аудит"
        verbose_name_plural = "Аудит"
        ordering = ("-created",)
