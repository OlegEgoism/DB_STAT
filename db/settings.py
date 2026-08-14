import os
import threading
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


def _local_database_host():
    """Return an explicit host override or Docker's host alias in a container."""
    configured_host = os.getenv("LOCAL_DATABASE_HOST", "").strip()
    if configured_host:
        return configured_host
    if Path("/.dockerenv").exists() or Path("/run/.containerenv").exists():
        return "host.docker.internal"
    return ""


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
DEBUG = _env_bool("DEBUG", True)
ALLOWED_HOSTS = _env_list("ALLOWED_HOSTS", "localhost,127.0.0.1,testserver")
CSRF_TRUSTED_ORIGINS = _env_list("CSRF_TRUSTED_ORIGINS") or _default_csrf_trusted_origins(ALLOWED_HOSTS)
CSRF_COOKIE_SECURE = _env_bool("CSRF_COOKIE_SECURE", False)
SESSION_COOKIE_SECURE = _env_bool("SESSION_COOKIE_SECURE", False)

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

DB_ENGINE = os.getenv("DB_ENGINE", "sqlite").strip().lower()
if DB_ENGINE == "postgresql":
    DATABASES = {
        "default": {"ENGINE": "django.db.backends.postgresql", "NAME": os.getenv("DB_NAME", "db_statistics"), "USER": os.getenv("DB_USER", "postgres"), "PASSWORD": os.getenv("DB_PASSWORD", ""), "HOST": os.getenv("DB_HOST", "localhost"), "PORT": int(os.getenv("DB_PORT", "5432"))}
    }
else:
    DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": os.getenv("SQLITE_NAME", BASE_DIR / "db.sqlite3")}}

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

# DB STAT application configuration
#
# These values are shared by the view modules and their helpers. Keeping them in
# Django settings provides one configuration source instead of module-level
# state scattered through the application.
CONNECTION_TIMEOUT_SECONDS = 5
ADMIN_ROLE = "Администратор"

SESSION_USER_ID_KEY = "db_user_id"
DEFAULT_SESSION_DURATION_HOURS = 8
MIN_SESSION_DURATION_MINUTES = 10
MAX_SESSION_DURATION_HOURS = 24
MIN_SESSION_DURATION_SECONDS = MIN_SESSION_DURATION_MINUTES * 60
MAX_SESSION_DURATION_SECONDS = MAX_SESSION_DURATION_HOURS * 60 * 60
SESSION_EXPIRES_AT_KEY = "session_expires_at"

LOCALHOST_NAMES = {"localhost", "127.0.0.1", "::1"}
# Docker images automatically translate loopback to the host alias even when
# an orchestrator omits or clears LOCAL_DATABASE_HOST. Native development keeps
# the value empty and therefore continues to use the machine's own loopback.
LOCAL_DATABASE_HOST = _local_database_host()

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

MAINTENANCE_JOB_EXECUTOR = ThreadPoolExecutor(
    max_workers=4, thread_name_prefix="db-stat-vacuum"
)
MAINTENANCE_JOBS = {}
MAINTENANCE_JOBS_LOCK = threading.Lock()
