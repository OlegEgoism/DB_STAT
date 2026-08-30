import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent


def _env_bool(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_list(name, default=""):
    return [item.strip() for item in os.getenv(name, default).split(",") if item.strip()]


def _default_csrf_trusted_origins(hosts):
    origins = []
    for host in hosts:
        if host in {"*", "testserver"}:
            continue
        normalized_host = host[1:] if host.startswith(".") else host
        if not normalized_host:
            continue
        wildcard_host = f"*.{normalized_host}" if host.startswith(".") else normalized_host
        origins.extend([f"http://{wildcard_host}", f"https://{wildcard_host}"])
    return origins


SECRET_KEY = os.getenv("SECRET_KEY", "django-insecure-dev-only-change-me")
# Небезопасно по умолчанию для продакшена: DEBUG включает подробные страницы
# ошибок со стектрейсами и настройками. Явно задавайте DEBUG=True в .env только
# для локальной разработки.
DEBUG = _env_bool("DEBUG", False)
ALLOWED_HOSTS = _env_list("ALLOWED_HOSTS", "localhost,127.0.0.1,testserver")
CSRF_TRUSTED_ORIGINS = _env_list("CSRF_TRUSTED_ORIGINS") or _default_csrf_trusted_origins(ALLOWED_HOSTS)
CSRF_COOKIE_SECURE = _env_bool("CSRF_COOKIE_SECURE", False)
SESSION_COOKIE_SECURE = _env_bool("SESSION_COOKIE_SECURE", False)
# Не включены по умолчанию, чтобы не ломать инсталляции без TLS-терминации
# (например, доступ по http внутри локальной сети). За обратным прокси с TLS
# задайте эти переменные окружения в .env.
SECURE_SSL_REDIRECT = _env_bool("SECURE_SSL_REDIRECT", False)
SECURE_HSTS_SECONDS = int(os.getenv("SECURE_HSTS_SECONDS", "0"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = _env_bool("SECURE_HSTS_INCLUDE_SUBDOMAINS", False)
SECURE_HSTS_PRELOAD = _env_bool("SECURE_HSTS_PRELOAD", False)
if _env_bool("SECURE_PROXY_SSL_HEADER", False):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

INSTALLED_APPS = ["django.contrib.admin", "django.contrib.auth", "django.contrib.contenttypes", "django.contrib.sessions", "django.contrib.messages", "django.contrib.staticfiles", "db_statistics.apps.DbStatisticsConfig"]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "db.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {"context_processors": ["django.template.context_processors.request", "django.contrib.auth.context_processors.auth", "django.contrib.messages.context_processors.messages"]},
    }
]

WSGI_APPLICATION = "db.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.getenv("SQLITE_NAME", BASE_DIR / "db.sqlite3"),
        "OPTIONS": {"timeout": 20},
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = os.getenv("LANGUAGE_CODE", "ru")
LANGUAGES = [("ru", "Русский"), ("en", "English")]
LOCALE_PATHS = [BASE_DIR / "locale"]
TIME_ZONE = os.getenv("TIME_ZONE", "Europe/Minsk")
USE_I18N = True
USE_TZ = True

DB_CONNECTION_ENCRYPTION_KEY = os.getenv("DB_CONNECTION_ENCRYPTION_KEY", SECRET_KEY)

STATIC_URL = os.getenv("STATIC_URL", "static/")
STATICFILES_DIRS = [BASE_DIR / "static"]

CONNECTION_TIMEOUT_SECONDS = 5
ADMIN_ROLE = "Администратор"

SESSION_USER_ID_KEY = "db_user_id"
DEFAULT_SESSION_DURATION_HOURS = 8
MIN_SESSION_DURATION_MINUTES = 10
MAX_SESSION_DURATION_HOURS = 24
MIN_SESSION_DURATION_SECONDS = MIN_SESSION_DURATION_MINUTES * 60
MAX_SESSION_DURATION_SECONDS = MAX_SESSION_DURATION_HOURS * 60 * 60
SESSION_EXPIRES_AT_KEY = "session_expires_at"

# После этого числа подряд неверных попыток ввода пароля вход для пользователя
# блокируется на LOGIN_LOCKOUT_SECONDS.
LOGIN_MAX_FAILED_ATTEMPTS = 5
LOGIN_LOCKOUT_SECONDS = 5 * 60

LOCALHOST_NAMES = {"localhost", "::1"}
LOCALHOST_DB_HOST = (
    os.getenv("LOCALHOST_DB_HOST", "127.0.0.1").strip() or "127.0.0.1"
)

SIDEBAR_TAB_IDS = [
    "database-overview",
    "segments",
    "databases",
    "tables",
    "views",
    "functions",
    "temp-tables",
    "distribution",
    "queries",
    "sessions",
    "locks",
    "transactions",
    "memory",
    "users",
    "groups",
    "maintenance",
    "favorites",
    "audit",
    "settings",
]
SIDEBAR_SECTION_IDS = [
    "infrastructure",
    "data",
    "performance",
    "administration",
    "additional",
]
FIXED_SIDEBAR_TAB_IDS = {"settings"}
SIDEBAR_TAB_LABELS = {
    "database-overview": "База данных",
    "segments": "Сегменты",
    "databases": "Схемы",
    "tables": "Таблицы",
    "views": "Представления",
    "functions": "Функции",
    "temp-tables": "Временные таблицы",
    "distribution": "Распределение",
    "queries": "Активные запросы",
    "sessions": "Сессии",
    "locks": "Блокировки",
    "transactions": "Транзакции",
    "memory": "Память",
    "users": "Пользователи",
    "groups": "Группы",
    "maintenance": "Обслуживание",
    "favorites": "Избранное",
    "audit": "Аудит",
    "settings": "Настройки",
}
SUPPORTED_LANGUAGES = {"ru", "en"}

# Каждый процесс приложения (в том числе каждый воркер WSGI-сервера при
# многопроцессном запуске) держит свой собственный пул из 4 потоков и на
# старте (см. db_statistics/apps.py) пытается забрать задачи со статусом
# "queued"/"running". Безопасность обеспечивает не сам пул, а атомарный захват
# задачи в _run_maintenance_operation (UPDATE ... WHERE status = 'queued'):
# только один процесс/поток успешно переводит задачу в "running", остальные
# получают 0 обновлённых строк и выходят. WAL-режим SQLite (см. apps.py)
# снижает вероятность "database is locked" при таких конкурентных обновлениях.
MAINTENANCE_JOB_EXECUTOR = ThreadPoolExecutor(
    max_workers=4, thread_name_prefix="db-stat-vacuum"
)
