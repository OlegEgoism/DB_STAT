"""Фильтры журналирования для db/settings.py (LOGGING)."""

import logging


class ServiceUnavailableWarningFilter(logging.Filter):
    """Понижает ответы 503 с ERROR до WARNING в журнале django.request.

    Django логирует каждый ответ 5xx как ERROR. Но 503 здесь — намеренный ответ
    приложения: заблокированный объект, превышенный таймаут или исчерпанный пул
    соединений к целевой БД. Это не сбой приложения, поэтому такая запись должна
    быть WARNING. Ответы 500 и прочие 5xx остаются ERROR.

    Django передаёт статус в ``extra`` (атрибут ``status_code``) и формирует
    сообщение вида ``"Service Unavailable: /path/"``; совпадение по любому из
    двух признаков считается 503.
    """

    def filter(self, record):
        if record.levelno == logging.ERROR and _is_service_unavailable(record):
            record.levelno = logging.WARNING
            record.levelname = logging.getLevelName(logging.WARNING)
        return True


def _is_service_unavailable(record):
    if getattr(record, "status_code", None) == 503:
        return True
    return record.getMessage().startswith("Service Unavailable")
