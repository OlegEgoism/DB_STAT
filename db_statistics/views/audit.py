"""Audit-log writing and formatting helpers.

Split out of views/helpers.py (see its module docstring).
"""

from django.utils import timezone

from db_statistics.models import DBAudit, DBFavorite
from db_statistics.views.pool import _normalize_database_host

MAINTENANCE_OPERATION_LABELS = {"vacuum": "VACUUM", "vacuum_full": "VACUUM FULL", "analyze": "ANALYZE", "explain_analyze": "EXPLAIN ANALYZE"}


def _audit_username(db_user=None, fallback="Неизвестный пользователь"):
    """Определяет имя пользователя для записи аудита"""
    if db_user:
        return db_user.login
    return fallback


def _write_audit(action_type, info, db_user=None, username=None):
    """Записывает событие в журнал аудита"""
    DBAudit.objects.create(username=username or _audit_username(db_user), action_type=action_type, info=info, created=timezone.now())


def _audit_action_label(action_type):
    """Возвращает отображаемое название действия аудита"""
    return dict(DBAudit.ACTION_TYPES).get(action_type, action_type)


def _format_audit_details(pairs):
    """Собирает список пар (метка, значение) в строку описания события аудита"""
    return "; ".join(f"{label}: {value}" for label, value in pairs)


def _connection_audit_fields(connection, *, server_label=False):
    """Возвращает базовые поля подключения, общие для разных записей аудита"""
    host_field = ("Сервер", f"{_normalize_database_host(connection.host)}:{connection.port}") if server_label else ("Хост", connection.host)
    fields = [("Подключение", connection.name), ("Тип БД", connection.db_type), host_field]
    if not server_label:
        fields.append(("Порт", connection.port))
    fields.append(("База данных", connection.database))
    fields.append(("Пользователь БД", connection.username))
    return fields


def _connection_audit_info(action, connection, *, result=None, error=None):
    """Формирует описание операции с подключением для аудита"""
    pairs = [("Действие", action), *_connection_audit_fields(connection)]
    if result:
        pairs.append(("Результат", result))
    if error:
        pairs.append(("Ошибка", error))
    return _format_audit_details(pairs)


def _favorite_audit_info(action, connection, object_type, object_key):
    """Формирует описание изменения избранного для аудита"""
    object_type_label = dict(DBFavorite.OBJECT_TYPES).get(object_type, object_type)
    return _format_audit_details([("Действие", action), ("Подключение", connection.name), ("Тип объекта", object_type_label), ("Идентификатор объекта", object_key)])


def _backend_termination_audit_info(action, connection, row):
    """Формирует описание завершения процесса базы данных для аудита"""
    client_address = str(row[5]) if row[5] else "local"
    client = f"{client_address}:{row[6]}" if row[6] is not None else client_address
    return _format_audit_details(
        [
            ("Действие", action),
            *_connection_audit_fields(connection, server_label=True),
            ("PID", row[1]),
            ("Пользователь сессии", row[2] or "—"),
            ("База сессии", row[3] or "—"),
            ("Приложение", row[4] or "—"),
            ("Клиент", client),
            ("Состояние", row[7] or "—"),
            ("Тип backend", row[8] or "—"),
            ("Начало сессии", row[9] or "—"),
            ("Начало транзакции", row[10] or "—"),
            ("Начало запроса", row[11] or "—"),
            ("Последнее изменение состояния", row[12] or "—"),
            ("Ожидание", " / ".join(part for part in [row[13], row[14]] if part) or "—"),
            ("Длительность сессии", row[15] or "—"),
            ("Длительность запроса", row[16] or "—"),
            ("SQL", row[17] or "—"),
            ("Результат", "успешно завершено"),
        ]
    )


def _maintenance_operation_audit_info(operation, connection, schema_name, table_name, result, error=None):
    """Формирует описание фоновой операции обслуживания для аудита"""
    operation_label = MAINTENANCE_OPERATION_LABELS.get(operation, operation.upper())
    pairs = [("Действие", operation_label), *_connection_audit_fields(connection, server_label=True), ("Схема", schema_name), ("Таблица", table_name), ("Результат", result)]
    if error:
        pairs.append(("Ошибка", error))
    return _format_audit_details(pairs)
