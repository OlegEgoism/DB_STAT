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
