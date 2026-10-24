"""Общая обвязка запросов и ответов: разбор JSON-тела запроса и сериализация подключения.

Настройки бокового меню и клиентские данные пользователя живут в views/sidebar.py, форматирование
размеров и длительностей — в views/formatting.py, подключения и запросы к целевой БД — в views/pool.py,
сессии, права и rate limit — в views/auth.py, аудит — в views/audit.py, пагинация и фильтры списков —
в views/pagination.py, фоновые задачи обслуживания — в views/maintenance.py.
"""

import json

# Реэкспорт для views/reports.py, который пока импортирует форматтер отсюда; новый код берёт его из formatting.py.
from db_statistics.views.formatting import _format_bytes  # noqa: F401


def _connection_to_dict(connection):
    """Преобразует подключение в словарь для JSON-ответа"""
    return {
        "id": str(connection.pk),
        "name": connection.name,
        "host": connection.host,
        "port": connection.port,
        "database": connection.database,
        "user": connection.username,
        "db_type": connection.db_type,
        "created_by": (connection.created_user.login if connection.created_user else None),
        "created_by_id": connection.created_user_id,
        "status": "offline",
    }


def _read_json_body(request):
    """Безопасно читает JSON-объект из тела запроса"""
    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {}
    # JSON также допускает массивы и скаляры, но API ожидает только объект.
    return payload if isinstance(payload, dict) else {}
