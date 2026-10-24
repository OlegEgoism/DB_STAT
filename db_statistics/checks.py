from django.conf import settings
from django.core.checks import Warning, register


@register()
def check_secret_key_default(app_configs, **kwargs):
    """Предупреждает (не блокирует запуск), если SECRET_KEY не задан явно.

    DB_CONNECTION_ENCRYPTION_KEY по умолчанию равен SECRET_KEY (см.
    settings.py) и шифрует сохранённые пароли к подключениям — на дефолтном
    значении это одинаковый, публично известный ключ у каждой инсталляции из
    образа. Это осознанный компромисс ради рабочего запуска "из коробки";
    предупреждение просто делает риск видимым в manage.py check и в логах.
    """
    if settings.SECRET_KEY != "django-insecure-dev-only-change-me":
        return []
    return [
        Warning(
            "SECRET_KEY не задан — используется публичный дефолт из образа.",
            hint="Сохранённые пароли к подключениям шифруются этим же ключом (DB_CONNECTION_ENCRYPTION_KEY), поэтому на инсталляции, доступной не только вам, задайте свой SECRET_KEY через переменную окружения.",
            id="db_statistics.W002",
        )
    ]


@register()
def check_cookie_transport_security(app_configs, **kwargs):
    """Предупреждает (не блокирует запуск), если куки CSRF/сессии могут уйти по HTTP.

    Не меняет сами значения по умолчанию: инсталляции без TLS-терминации во
    внутренней сети — законный сценарий (см. комментарий у SECURE_SSL_REDIRECT
    в settings.py), поэтому включать *_COOKIE_SECURE принудительно нельзя —
    это молча сломало бы вход на таких инсталляциях. Предупреждение просто
    делает риск видимым в `manage.py check` (и в CI) для тех, кто разворачивает
    это наружу и забыл включить их.
    """
    if settings.DEBUG:
        return []
    if settings.CSRF_COOKIE_SECURE and settings.SESSION_COOKIE_SECURE:
        return []
    return [
        Warning(
            "CSRF_COOKIE_SECURE и/или SESSION_COOKIE_SECURE выключены при DEBUG=False.",
            hint="Нормально для внутренней инсталляции без TLS. Если сервер доступен из интернета, задайте в .env CSRF_COOKIE_SECURE=True, SESSION_COOKIE_SECURE=True и SECURE_SSL_REDIRECT=True, чтобы куки не уходили по обычному HTTP.",
            id="db_statistics.W001",
        )
    ]


# Больше этого числа соединений на один пул — повод проверить бюджет (см. .env.example).
CONNECTION_POOL_MAX_CONN_WARNING_THRESHOLD = 20


@register()
def check_connection_pool_budget(app_configs, **kwargs):
    """Предупреждает (не блокирует запуск), если пул к целевой БД может открыть слишком много соединений.

    Каждый воркер gunicorn держит свой пул на каждое сохранённое подключение, поэтому
    итоговая нагрузка на целевую БД ≈ GUNICORN_WORKERS × DB_CONNECTION_POOL_MAX_CONN ×
    число используемых подключений. Высокое значение легко исчерпывает max_connections
    на целевой БД (особенно на Greenplum), поэтому предупреждаем, а не запрещаем.
    """
    limit = settings.DB_CONNECTION_POOL_MAX_CONN
    if limit <= CONNECTION_POOL_MAX_CONN_WARNING_THRESHOLD:
        return []
    return [
        Warning(
            f"DB_CONNECTION_POOL_MAX_CONN={limit} больше {CONNECTION_POOL_MAX_CONN_WARNING_THRESHOLD}.",
            hint="Пул открывает до этого числа соединений на каждое сохранённое подключение в каждом воркере gunicorn. Проверьте бюджет: GUNICORN_WORKERS × DB_CONNECTION_POOL_MAX_CONN × число подключений должно укладываться в max_connections целевой БД (см. .env.example).",
            id="db_statistics.W003",
        )
    ]


@register()
def check_encryption_key_separate(app_configs, **kwargs):
    """Предупреждает, если ключ шифрования паролей подключений совпадает с SECRET_KEY.

    По умолчанию DB_CONNECTION_ENCRYPTION_KEY берётся из SECRET_KEY: один секрет тогда защищает
    и подписи сессий, и сохранённые пароли к целевым базам. Для рабочей инсталляции задайте
    DB_CONNECTION_ENCRYPTION_KEY отдельно. Это только предупреждение: смена ключа без
    перешифрования сделает сохранённые пароли нечитаемыми.
    """
    if settings.DEBUG:
        return []
    if settings.DB_CONNECTION_ENCRYPTION_KEY != settings.SECRET_KEY:
        return []
    return [
        Warning(
            "DB_CONNECTION_ENCRYPTION_KEY совпадает с SECRET_KEY.",
            hint="Один секрет защищает подписи сессий и сохранённые пароли к целевым базам. Задайте DB_CONNECTION_ENCRYPTION_KEY отдельно до первого сохранения подключений; после смены ключ нужно перешифровать пароли (manage.py encrypt_connection_passwords работает только с открытыми паролями).",
            id="db_statistics.W004",
        )
    ]
