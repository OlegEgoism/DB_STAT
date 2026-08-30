import base64
import hashlib
import uuid

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.db import models

ENCRYPTED_PASSWORD_PREFIX = "enc$"


def vn(name: str, help_text: str, **kwargs) -> dict:
    """Возвращает единые подпись и пояснение поля для интерфейса Django"""
    return {"verbose_name": name, "help_text": help_text, **kwargs}


# Фиксированная соль приложения для PBKDF2. Соль не обязана быть секретной или
# случайной для каждой инсталляции — её роль здесь только в том, чтобы ключ
# шифрования не совпадал с сырым значением секрета и требовал дорогостоящего
# растяжения (много итераций), что затрудняет офлайн-подбор при низкой
# энтропии DB_CONNECTION_ENCRYPTION_KEY/SECRET_KEY.
_CONNECTION_PASSWORD_KDF_SALT = b"db-stat:connection-password:v1"
_CONNECTION_PASSWORD_KDF_ITERATIONS = 390_000


def _connection_encryption_secret():
    """Возвращает секрет, из которого выводится ключ шифрования паролей подключений"""
    return str(getattr(settings, "DB_CONNECTION_ENCRYPTION_KEY", "") or settings.SECRET_KEY)


def _connection_password_cipher():
    """Создаёт экземпляр шифра на основе ключа, растянутого через PBKDF2"""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=_CONNECTION_PASSWORD_KDF_SALT,
        iterations=_CONNECTION_PASSWORD_KDF_ITERATIONS,
    )
    key = base64.urlsafe_b64encode(kdf.derive(_connection_encryption_secret().encode("utf-8")))
    return Fernet(key)


def _legacy_connection_password_cipher():
    """Шифр на основе прежнего вывода ключа (sha256 без растяжения), только для чтения старых записей"""
    key = base64.urlsafe_b64encode(hashlib.sha256(_connection_encryption_secret().encode("utf-8")).digest())
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
    """Расшифровывает пароль подключения.

    Сначала пробует текущий (PBKDF2) ключ, а при неудаче — прежний sha256-ключ,
    чтобы подключения, зашифрованные до перехода на PBKDF2, не сломались.
    """
    if stored_password in (None, ""):
        return stored_password or ""
    text = str(stored_password)
    if not text.startswith(ENCRYPTED_PASSWORD_PREFIX):
        return text
    token = text[len(ENCRYPTED_PASSWORD_PREFIX):].encode("utf-8")
    try:
        return _connection_password_cipher().decrypt(token).decode("utf-8")
    except InvalidToken:
        pass
    try:
        return _legacy_connection_password_cipher().decrypt(token).decode("utf-8")
    except InvalidToken:
        return ""


# ============================================================================
# АБСТРАКЦИИ
# ============================================================================
class DateStamp(models.Model):
    """Временные отметки"""

    created = models.DateTimeField(**vn("Дата создания", "Дата и время создания записи"), auto_now_add=True)
    updated = models.DateTimeField(**vn("Дата изменения", "Дата и время последнего изменения записи"), auto_now=True)

    class Meta:
        abstract = True


class Active(models.Model):
    """Статус активности"""

    is_active = models.BooleanField(**vn("Активность", "Определяет, доступна ли запись для использования в приложении"), default=True)

    class Meta:
        abstract = True


# ============================================================================
# МОДЕЛИ
# ============================================================================
class DBUser(DateStamp, Active):
    """Пользователь"""

    USER_ROLE = [("Администратор", "Администратор"), ("Аналитик", "Аналитик")]

    login = models.CharField(**vn("Логин", "Уникальное имя пользователя для входа в DB STAT"), max_length=100, db_index=True, unique=True)
    email = models.EmailField(**vn("Почта", "Уникальный адрес электронной почты пользователя"), unique=True)
    password = models.CharField(**vn("Пароль", "Хэш пароля пользователя для входа в DB STAT"), max_length=128, blank=True, default="")
    role = models.CharField(**vn("Роль", "Роль определяет доступные пользователю действия"), max_length=20, choices=USER_ROLE, default="Аналитик")
    connections = models.ManyToManyField(to="db_statistics.DBConnection", **vn("Подключения к базам данных", "Подключения, доступные этому пользователю"), blank=True)
    failed_login_attempts = models.PositiveIntegerField(**vn("Неудачные попытки входа", "Количество подряд неверных попыток ввода пароля с момента последнего успешного входа"), default=0)
    lockout_until = models.DateTimeField(**vn("Заблокирован до", "Пока не истечёт это время, вход для пользователя запрещён из-за подбора пароля"), null=True, blank=True)

    class Meta:
        db_table = "db_user"
        verbose_name = "Пользователь"
        verbose_name_plural = "Пользователи"
        ordering = ["login"]

    def __str__(self):
        return self.login

    def set_password(self, raw_password):
        """Хэширует и сохраняет пароль (не забудьте вызвать save())"""
        self.password = make_password(raw_password)

    def check_password(self, raw_password):
        """Проверяет пароль по сохранённому хэшу"""
        return bool(self.password) and check_password(raw_password, self.password)


class DBUserSidebarSettings(DateStamp):
    """Настройки сайдбара """

    user = models.OneToOneField(to="db_statistics.DBUser", **vn("Пользователь", "Пользователь, которому принадлежат настройки бокового меню"), related_name="user_db_user_sidebar_settings", on_delete=models.CASCADE)
    visible_tabs = models.JSONField(**vn("Видимые вкладки", "Сохранённый порядок и набор доступных вкладок бокового меню"), default=list, blank=True)

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

    user = models.ForeignKey(to="db_statistics.DBUser", **vn("Пользователь", "Пользователь, добавивший объект в избранное"), related_name="user_db_favorite", on_delete=models.CASCADE)
    connection = models.ForeignKey(to="db_statistics.DBConnection", **vn("Подключение", "Подключение, в котором находится избранный объект"), related_name="connection_db_favorite", on_delete=models.CASCADE)
    object_type = models.CharField(**vn("Тип объекта", "Категория избранного объекта базы данных"), max_length=16, choices=OBJECT_TYPES)
    object_key = models.CharField(**vn("Идентификатор объекта", "Стабильный составной ключ объекта внутри подключения"), max_length=512)

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

    name = models.CharField(**vn("Название", "Понятное пользователю название подключения"), max_length=120)
    host = models.CharField(**vn("Хост", "Имя хоста или IP-адрес сервера базы данных"), max_length=255)
    port = models.PositiveIntegerField(**vn("Порт", "TCP-порт сервера базы данных"), default=5432)
    database = models.CharField(**vn("База данных", "Имя целевой базы данных для мониторинга"), max_length=120)
    username = models.CharField(**vn("Пользователь", "Имя пользователя целевой базы данных"), max_length=120)
    password = models.CharField(**vn("Пароль", "Зашифрованный пароль пользователя целевой базы данных."), max_length=255)
    db_type = models.CharField(**vn("Тип базы данных", "Тип подключаемой PostgreSQL-совместимой СУБД."), max_length=20, choices=DATABASE_TYPES, default=POSTGRESQL)
    created_user = models.ForeignKey(to="db_statistics.DBUser", **vn("Создатель подключения", "Пользователь DB STAT, создавший подключение."), related_name="created_user_db_connection", on_delete=models.SET_NULL, null=True, blank=True)

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
        """Поддерживает ли СУБД функции распределённого кластера Greenplum"""
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

    username = models.CharField(**vn("Пользователь", "Логин пользователя, выполнившего действие."), max_length=200)
    action_type = models.CharField(**vn("Действие", "Тип события, сохранённого в журнале аудита."), max_length=32, choices=ACTION_TYPES)
    info = models.TextField(**vn("Информация", "Подробное безопасное описание выполненного действия."))
    created = models.DateTimeField(**vn("Дата действия", "Дата и время выполнения действия."))

    def __str__(self):
        return f"{self.username} - {self.action_type}"

    class Meta:
        db_table = "db_audit"
        verbose_name = "Аудит"
        verbose_name_plural = "Аудит"
        ordering = ("-created",)


class MaintenanceJob(models.Model):
    """Фоновые операции обслуживания"""

    STATUS_CHOICES = [
        ("queued", "В очереди"),
        ("running", "Выполняется"),
        ("completed", "Завершено"),
        ("failed", "Ошибка"),
    ]
    OPERATION_CHOICES = [
        ("vacuum", "VACUUM"),
        ("vacuum_full", "VACUUM FULL"),
        ("analyze", "ANALYZE"),
        ("explain_analyze", "EXPLAIN ANALYZE"),
    ]

    id = models.UUIDField(**vn("Идентификатор", "Уникальный идентификатор фоновой задачи."), primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(DBUser, **vn("Пользователь", "Пользователь, запустивший операцию обслуживания."), on_delete=models.SET_NULL, null=True, related_name="maintenance_jobs")
    connection = models.ForeignKey(DBConnection, **vn("Подключение", "Подключение к базе данных, где выполняется операция."), on_delete=models.CASCADE, related_name="maintenance_jobs")
    operation = models.CharField(**vn("Операция", "Команда обслуживания, помещённая в очередь."), max_length=32, choices=OPERATION_CHOICES)
    schema_name = models.CharField(**vn("Схема", "Имя схемы обслуживаемой таблицы."), max_length=255)
    table_name = models.CharField(**vn("Таблица", "Имя обслуживаемой таблицы."), max_length=255)
    status = models.CharField(**vn("Статус", "Текущее состояние задачи в устойчивой очереди."), max_length=16, choices=STATUS_CHOICES, default="queued", db_index=True)
    message = models.TextField(**vn("Сообщение", "Текущее или итоговое сообщение исполнителя."), default="Операция ожидает выполнения")
    details = models.JSONField(**vn("Подробности", "Дополнительные строки результата, включая план EXPLAIN."), default=list, blank=True)
    statistics = models.JSONField(**vn("Статистика", "Снимок статистики таблицы после выполнения операции."), null=True, blank=True)
    duration_seconds = models.FloatField(**vn("Длительность, с", "Продолжительность выполнения операции в секундах."), null=True, blank=True)
    created = models.DateTimeField(**vn("Дата создания", "Дата и время постановки задачи в очередь."), auto_now_add=True, db_index=True)
    started = models.DateTimeField(**vn("Дата запуска", "Дата и время начала выполнения задачи."), null=True, blank=True)
    finished = models.DateTimeField(**vn("Дата завершения", "Дата и время успешного или ошибочного завершения задачи."), null=True, blank=True)

    class Meta:
        db_table = "db_maintenance_job"
        verbose_name = "Фоновая операция обслуживания"
        verbose_name_plural = "Фоновые операции обслуживания"
        ordering = ("-created",)

    def __str__(self):
        return f"{self.get_operation_display()} {self.schema_name}.{self.table_name} — {self.get_status_display()}"
