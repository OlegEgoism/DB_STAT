"""Shared constants and helper functions for DB STAT views.

Keeping infrastructure, session, audit, connection and query helpers here makes
``views.py`` focus on HTTP endpoints and their response payloads.
"""

import json
import logging
import time
from contextlib import closing, contextmanager
from decimal import Decimal, InvalidOperation

import psycopg2
from django.conf import settings
from django.db import close_old_connections
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from psycopg2 import sql

from db_statistics.models import DBAudit, DBConnection, DBFavorite, DBUser, DBUserSidebarSettings, MaintenanceJob

logger = logging.getLogger(__name__)

# Служебные схемы, которые не показываются пользователю как обычные объекты БД.
EXCLUDED_SYSTEM_SCHEMAS_SQL = "('pg_catalog', 'information_schema', 'gp_toolkit')"


def _normalize_database_host(host):
    """Нормализует имя хоста базы данных для локальных подключений"""
    normalized_host = (host or "").strip().lower()
    if normalized_host in settings.LOCALHOST_NAMES:
        return settings.LOCALHOST_DB_HOST
    return host


def _current_db_user(request):
    """Возвращает активного пользователя приложения из текущей сессии"""
    if _session_has_expired(request.session):
        request.session.flush()
        return None
    user_id = request.session.get(settings.SESSION_USER_ID_KEY)
    if not user_id:
        return None
    try:
        return DBUser.objects.get(pk=user_id, is_active=True)
    except DBUser.DoesNotExist:
        request.session.pop(settings.SESSION_USER_ID_KEY, None)
        return None


def _normalize_sidebar_tabs(tabs):
    """Проверяет и нормализует список вкладок бокового меню"""
    if not isinstance(tabs, list):
        return settings.SIDEBAR_TAB_IDS.copy()
    normalized_tabs = list(
        dict.fromkeys(tab for tab in tabs if tab in settings.SIDEBAR_TAB_IDS)
    )
    if not any(tab not in settings.FIXED_SIDEBAR_TAB_IDS for tab in normalized_tabs):
        return settings.SIDEBAR_TAB_IDS.copy()
    normalized_tabs.extend(
        tab
        for tab in settings.SIDEBAR_TAB_IDS
        if tab in settings.FIXED_SIDEBAR_TAB_IDS and tab not in normalized_tabs
    )
    return normalized_tabs


def _normalize_sidebar_sections(sections):
    """Проверяет и нормализует порядок разделов бокового меню"""
    if not isinstance(sections, list):
        return settings.SIDEBAR_SECTION_IDS.copy()
    normalized_sections = list(
        dict.fromkeys(
            section for section in sections if section in settings.SIDEBAR_SECTION_IDS
        )
    )
    normalized_sections.extend(
        section
        for section in settings.SIDEBAR_SECTION_IDS
        if section not in normalized_sections
    )
    return normalized_sections


def _sidebar_settings_values(sidebar_settings):
    """Извлекает нормализованные значения настроек бокового меню"""
    stored_value = sidebar_settings.visible_tabs
    if isinstance(stored_value, dict):
        return (
            _normalize_sidebar_tabs(stored_value.get("visible_tabs")),
            _normalize_sidebar_sections(stored_value.get("section_order")),
        )
    return _normalize_sidebar_tabs(stored_value), settings.SIDEBAR_SECTION_IDS.copy()


def _session_duration_seconds(value):
    """Преобразует длительность сессии из часов в секунды"""
    try:
        seconds = int(Decimal(str(value)) * 60 * 60)
    except (InvalidOperation, TypeError, ValueError):
        return None
    if (
        not settings.MIN_SESSION_DURATION_SECONDS
        <= seconds
        <= settings.MAX_SESSION_DURATION_SECONDS
    ):
        return None
    return seconds


def _session_has_expired(session, now_timestamp=None):
    """Проверяет, истёк ли срок действия пользовательской сессии"""
    expires_at = session.get(settings.SESSION_EXPIRES_AT_KEY)
    if not expires_at:
        return False
    try:
        expires_at = int(expires_at)
    except (TypeError, ValueError):
        return True
    current_timestamp = (
        int(timezone.now().timestamp()) if now_timestamp is None else int(now_timestamp)
    )
    return expires_at <= current_timestamp


def _sidebar_tab_labels(tab_ids):
    """Возвращает отображаемые названия вкладок бокового меню"""
    return [settings.SIDEBAR_TAB_LABELS.get(tab_id, tab_id) for tab_id in tab_ids]


def _available_sidebar_tabs_for_user(db_user):
    """Возвращает вкладки, доступные пользователю с учётом его роли"""
    if db_user.role == settings.ADMIN_ROLE:
        return settings.SIDEBAR_TAB_IDS.copy()
    return [tab_id for tab_id in settings.SIDEBAR_TAB_IDS if tab_id != "audit"]


def _sidebar_settings_values_for_user(sidebar_settings, db_user):
    """Фильтрует настройки бокового меню по правам пользователя"""
    visible_tabs, section_order = _sidebar_settings_values(sidebar_settings)
    available_tabs = set(_available_sidebar_tabs_for_user(db_user))
    return [
        tab_id for tab_id in visible_tabs if tab_id in available_tabs
    ], section_order


def _sidebar_settings_audit_info(db_user, visible_tabs, previous_tabs):
    """Формирует описание изменения настроек бокового меню для аудита"""
    visible_labels = ", ".join(_sidebar_tab_labels(visible_tabs))
    previous_labels = ", ".join(_sidebar_tab_labels(previous_tabs))
    return (
        "Настройки сайдбара пользователя изменены: "
        f"Пользователь: {db_user.login}; "
        f"Отображаемые вкладки: {visible_labels}; "
        f"Предыдущие вкладки: {previous_labels}"
    )


def _sidebar_settings_for_user(db_user):
    """Получает или создаёт настройки бокового меню пользователя"""
    sidebar_settings, _created = DBUserSidebarSettings.objects.get_or_create(
        user=db_user,
        defaults={"visible_tabs": settings.SIDEBAR_TAB_IDS.copy()},
    )
    normalized_tabs, normalized_sections = _sidebar_settings_values(sidebar_settings)
    normalized_value = {
        "visible_tabs": normalized_tabs,
        "section_order": normalized_sections,
    }
    if sidebar_settings.visible_tabs != normalized_value:
        sidebar_settings.visible_tabs = normalized_value
        sidebar_settings.save(update_fields=["visible_tabs", "updated"])
    return sidebar_settings


def _user_payload(db_user):
    """Формирует клиентские данные текущего пользователя"""
    if not db_user:
        return None
    sidebar_settings = _sidebar_settings_for_user(db_user)
    visible_tabs, section_order = _sidebar_settings_values_for_user(
        sidebar_settings, db_user
    )
    return {
        "id": db_user.pk,
        "login": db_user.login,
        "email": db_user.email,
        "role": db_user.role,
        "can_manage_connections": db_user.role == settings.ADMIN_ROLE,
        "can_run_destructive_actions": db_user.role == settings.ADMIN_ROLE,
        "sidebar_visible_tabs": visible_tabs,
        "sidebar_section_order": section_order,
    }


def _connection_permission_error():
    """Возвращает ошибку недостаточных прав на управление подключениями"""
    return JsonResponse(
        {
            "ok": False,
            "message": "Создавать и редактировать подключения может только Администратор",
        },
        status=403,
    )


def _connection_delete_permission_error():
    """Возвращает ошибку недостаточных прав на удаление подключения"""
    return JsonResponse(
        {"ok": False, "message": "Удалять подключение может только его создатель"},
        status=403,
    )


def _connection_edit_permission_error():
    """Возвращает ошибку недостаточных прав на изменение подключения"""
    return JsonResponse(
        {
            "ok": False,
            "message": "Редактировать подключение может только его создатель",
        },
        status=403,
    )


def _audit_username(db_user=None, fallback="Неизвестный пользователь"):
    """Определяет имя пользователя для записи аудита"""
    if db_user:
        return db_user.login
    return fallback


def _write_audit(action_type, info, db_user=None, username=None):
    """Записывает событие в журнал аудита"""
    DBAudit.objects.create(
        username=username or _audit_username(db_user),
        action_type=action_type,
        info=info,
        created=timezone.now(),
    )


def _audit_action_label(action_type):
    """Возвращает отображаемое название действия аудита"""
    return dict(DBAudit.ACTION_TYPES).get(action_type, action_type)


def _format_audit_details(pairs):
    """Собирает список пар (метка, значение) в строку описания события аудита"""
    return "; ".join(f"{label}: {value}" for label, value in pairs)


def _connection_audit_fields(connection, *, server_label=False):
    """Возвращает базовые поля подключения, общие для разных записей аудита"""
    host_field = (
        ("Сервер", f"{_normalize_database_host(connection.host)}:{connection.port}")
        if server_label
        else ("Хост", connection.host)
    )
    fields = [
        ("Подключение", connection.name),
        ("Тип БД", connection.db_type),
        host_field,
    ]
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
    return _format_audit_details(
        [
            ("Действие", action),
            ("Подключение", connection.name),
            ("Тип объекта", object_type_label),
            ("Идентификатор объекта", object_key),
        ]
    )


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


MAINTENANCE_OPERATION_LABELS = {
    "vacuum": "VACUUM",
    "vacuum_full": "VACUUM FULL",
    "analyze": "ANALYZE",
    "explain_analyze": "EXPLAIN ANALYZE",
}


def _maintenance_operation_audit_info(
    operation, connection, schema_name, table_name, result, error=None
):
    """Формирует описание фоновой операции обслуживания для аудита"""
    operation_label = MAINTENANCE_OPERATION_LABELS.get(operation, operation.upper())
    pairs = [
        ("Действие", operation_label),
        *_connection_audit_fields(connection, server_label=True),
        ("Схема", schema_name),
        ("Таблица", table_name),
        ("Результат", result),
    ]
    if error:
        pairs.append(("Ошибка", error))
    return _format_audit_details(pairs)


def _can_manage_connections(request):
    """Проверяет право пользователя управлять подключениями"""
    db_user = _current_db_user(request)
    return bool(db_user and db_user.role == settings.ADMIN_ROLE)


def _destructive_action_permission_error(request):
    """Проверяет право пользователя выполнять разрушающие операции"""
    db_user = _current_db_user(request)
    if not db_user:
        return JsonResponse(
            {"ok": False, "message": "Требуется вход в приложение"}, status=401
        )
    if db_user.role != settings.ADMIN_ROLE:
        return JsonResponse(
            {"ok": False, "message": "Действие доступно только Администратору"},
            status=403,
        )
    return None


def _available_connections(request):
    """Возвращает доступные текущему пользователю подключения"""
    db_user = _current_db_user(request)
    if not db_user:
        return DBConnection.objects.none()
    return db_user.connections.filter(is_active=True).select_related("created_user")


def _get_connection_for_request(request, connection_id):
    """Получает доступное пользователю подключение по идентификатору"""
    return get_object_or_404(_available_connections(request), pk=connection_id)


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
        "created_by": (
            connection.created_user.login if connection.created_user else None
        ),
        "created_by_id": connection.created_user_id,
        "status": "offline",
    }


def _read_json_body(request):
    """Безопасно читает JSON-объект из тела запроса"""
    try:
        return json.loads(request.body.decode("utf-8") or "{}")
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {}


def _parse_pg_size_to_bytes(value, default_unit="B"):
    """Преобразует значение размера PostgreSQL в байты"""
    if value in (None, ""):
        return None
    text = str(value).strip()
    if not text:
        return None
    parts = text.split()
    if len(parts) == 1:
        number_part = "".join(ch for ch in text if ch.isdigit() or ch in ".,-")
        unit_part = text[len(number_part) :].strip() or default_unit
    else:
        number_part, unit_part = parts[0], parts[1]
    try:
        number = float(number_part.replace(",", ""))
    except ValueError:
        return None
    unit = unit_part.lower()
    multipliers = {
        "b": 1,
        "byte": 1,
        "bytes": 1,
        "kb": 1024,
        "kib": 1024,
        "mb": 1024**2,
        "mib": 1024**2,
        "gb": 1024**3,
        "gib": 1024**3,
        "tb": 1024**4,
        "tib": 1024**4,
    }
    return int(number * multipliers.get(unit, 1))


def _format_duration(value):
    """Форматирует интервал времени (timedelta) для отображения"""
    return str(value).split(".")[0] if value else "—"


def _duration_seconds(value):
    """Возвращает продолжительность интервала в секундах (0, если значение отсутствует)"""
    return max(int(value.total_seconds()), 0) if value else 0


def _format_bytes(size_bytes):
    """Форматирует размер в байтах для отображения"""
    if size_bytes is None:
        return "—"
    value = float(size_bytes)
    for unit in ["Б", "КБ", "МБ", "ГБ"]:
        if value < 1024:
            return f"{value:.2f} {unit}"
        value /= 1024
    return f"{value:.2f} ТБ"


def _safe_db_error_message(action_description, exc):
    """Логирует подробности ошибки БД и возвращает безопасное сообщение для клиента.

    Сырой текст исключения psycopg2/драйвера может содержать имена схем, таблиц
    и другие внутренние детали целевой БД, которые не должны попадать в ответ
    пользователю (в том числе Аналитику с ограниченным доступом).
    """
    logger.warning("%s", action_description, exc_info=exc)
    return f"{action_description}. Подробности см. в журнале сервера приложения"


def _list_query_params(payload, sort_columns, default_sort, *, default_page_size=100):
    """Разбирает общие параметры пагинации, поиска и сортировки для списковых запросов.

    Возвращает (page, page_size, offset, search, sort_column, direction).
    """
    page_size = int(payload.get("page_size") or default_page_size)
    page = max(int(payload.get("page") or 1), 1)
    offset = (page - 1) * page_size
    search = (payload.get("search") or "").strip()
    sort = payload.get("sort") or default_sort
    direction = "ASC" if payload.get("direction") == "asc" else "DESC"
    sort_column = sort_columns.get(sort, default_sort)
    return page, page_size, offset, search, sort_column, direction


def _escape_like_pattern(value):
    """Экранирует специальные символы шаблона SQL LIKE."""
    return value.replace("!", "!!").replace("%", "!%").replace("_", "!_")


def _like_search_pattern(value):
    """Возвращает безопасный шаблон для регистронезависимого поиска подстроки."""
    return f"%{_escape_like_pattern(value)}%"


def _multi_column_search_filter(search, columns):
    """Строит условие ILIKE по нескольким колонкам для текстового поиска.

    Возвращает (where_sql, params); where_sql уже начинается с ``AND``.
    """
    pattern = _like_search_pattern(search)
    clauses = " OR ".join(f"{column} ILIKE %s ESCAPE '!'" for column in columns)
    return f"AND ({clauses})", [pattern] * len(columns)


def _connection_kwargs(host, port, database, username, password, ssl=True):
    """Формирует параметры подключения psycopg2."""
    return {
        "host": _normalize_database_host(host),
        "port": port,
        "dbname": database,
        "user": username,
        "password": password,
        "connect_timeout": settings.CONNECTION_TIMEOUT_SECONDS,
        "sslmode": "prefer" if ssl else "disable",
    }


def _test_connection_params(host, port, database, username, password, ssl):
    """Проверяет подключение по переданным параметрам."""
    with closing(
        psycopg2.connect(**_connection_kwargs(host, port, database, username, password, ssl))
    ) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()


@contextmanager
def _open_database_connection(db_connection, ssl=True):
    """Открывает соединение с сохранённой базой данных и гарантированно закрывает его.

    В отличие от использования psycopg2-соединения напрямую как контекстного
    менеджера (который только коммитит/откатывает транзакцию, но не закрывает
    сокет), этот менеджер контекста явно закрывает соединение при выходе из
    блока `with`, независимо от того, как он завершился.
    """
    connection = psycopg2.connect(
        **_connection_kwargs(
            db_connection.host,
            db_connection.port,
            db_connection.database,
            db_connection.username,
            db_connection.get_password(),
            ssl,
        )
    )
    try:
        yield connection
    finally:
        connection.close()


def _fetch_db_rows(db_connection, query, params=None):
    """Выполняет запрос и возвращает все строки результата."""
    with _open_database_connection(db_connection) as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, params or [])
            return cursor.fetchall()


def _fetch_db_row(db_connection, query, params=None):
    """Выполняет запрос и возвращает первую строку результата."""
    with _open_database_connection(db_connection) as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, params or [])
            return cursor.fetchone()


def _fetch_db_resultsets(db_connection, *queries):
    """Выполняет несколько запросов в одном соединении."""
    resultsets = []
    with _open_database_connection(db_connection) as connection:
        with connection.cursor() as cursor:
            for query, params in queries:
                cursor.execute(query, params or [])
                resultsets.append(cursor.fetchall())
    return resultsets


def _serialize_maintenance_job(job):
    """Преобразует сохранённую задачу в безопасный ответ API."""
    return {
        "id": str(job.pk),
        "connection_id": job.connection_id,
        "connection_name": job.connection.name,
        "username": job.user.login if job.user else "—",
        "status": job.status,
        "operation": job.operation,
        "schema_name": job.schema_name,
        "table_name": job.table_name,
        "message": job.message,
        "details": job.details,
        "statistics": job.statistics,
        "duration_seconds": job.duration_seconds,
        "created": job.created.isoformat(),
        "started": job.started.isoformat() if job.started else None,
        "finished": job.finished.isoformat() if job.finished else None,
    }


def _submit_maintenance_job(job_id):
    settings.MAINTENANCE_JOB_EXECUTOR.submit(_run_maintenance_operation, str(job_id))


def _run_maintenance_operation(job_id):
    """Выполняет VACUUM/ANALYZE/EXPLAIN ANALYZE и обновляет состояние задачи."""
    close_old_connections()
    claimed = MaintenanceJob.objects.filter(pk=job_id, status="queued").update(
        status="running", message="Операция выполняется", started=timezone.now()
    )
    if not claimed:
        close_old_connections()
        return
    job = MaintenanceJob.objects.select_related("connection", "user").get(pk=job_id)
    connection_id = job.connection_id
    schema_name = job.schema_name
    table_name = job.table_name
    operation = job.operation
    username = job.user.login if job.user else "system"
    db_connection = None
    started_at = time.monotonic()
    try:
        db_connection = DBConnection.objects.get(pk=connection_id)
        table_identifier = sql.Identifier(schema_name, table_name)
        if operation in {"vacuum", "vacuum_full"}:
            statement = sql.SQL("VACUUM {mode} {table}").format(
                mode=sql.SQL("FULL") if operation == "vacuum_full" else sql.SQL(""),
                table=table_identifier,
            )
        elif operation == "analyze":
            statement = sql.SQL("ANALYZE {table}").format(table=table_identifier)
        else:
            statement = sql.SQL(
                "EXPLAIN (ANALYZE, BUFFERS, VERBOSE, FORMAT TEXT) SELECT * FROM {table}"
            ).format(table=table_identifier)
        # VACUUM запрещён внутри транзакции, поэтому autocommit включается
        # сразу после открытия соединения, до выполнения запроса.
        with _open_database_connection(db_connection) as connection:
            connection.autocommit = True
            with connection.cursor() as cursor:
                cursor.execute(statement)
                details = (
                    [str(row[0]) for row in cursor.fetchmany(500)]
                    if operation == "explain_analyze"
                    else []
                )
                # После VACUUM принудительно обновляем оценки планировщика.
                # В Greenplum/Greengage значения pg_stat_user_tables на
                # coordinator без ANALYZE могут оставаться устаревшими.
                if operation in {"vacuum", "vacuum_full"}:
                    cursor.execute(
                        sql.SQL("ANALYZE {table}").format(table=table_identifier)
                    )
                cursor.execute(
                    """
                    SELECT
                        COALESCE(n_live_tup, 0)::bigint,
                        COALESCE(n_dead_tup, 0)::bigint,
                        last_vacuum,
                        last_autovacuum,
                        last_analyze,
                        last_autoanalyze
                    FROM pg_catalog.pg_stat_user_tables
                    WHERE schemaname = %s AND relname = %s
                    """,
                    [schema_name, table_name],
                )
                statistics_row = cursor.fetchone()
                statistics = (
                    {
                        "live_rows": int(statistics_row[0]),
                        "dead_rows": int(statistics_row[1]),
                        "last_vacuum": max(
                            filter(None, (statistics_row[2], statistics_row[3])),
                            default=None,
                        ).isoformat() if any((statistics_row[2], statistics_row[3])) else None,
                        "last_analyze": max(
                            filter(None, (statistics_row[4], statistics_row[5])),
                            default=None,
                        ).isoformat() if any((statistics_row[4], statistics_row[5])) else None,
                        "is_estimate": True,
                    }
                    if statistics_row
                    else None
                )
    except Exception as exc:
        result = {"status": "failed", "message": str(exc), "details": []}
    else:
        result = {
            "status": "completed",
            "message": "Операция успешно завершена",
            "details": details,
            "statistics": statistics,
        }
    result["duration_seconds"] = round(time.monotonic() - started_at, 3)

    MaintenanceJob.objects.filter(pk=job_id).update(
        status=result["status"],
        message=result["message"],
        details=result.get("details", []),
        statistics=result.get("statistics"),
        duration_seconds=result["duration_seconds"],
        finished=timezone.now(),
    )

    if db_connection is not None:
        audit_info = _maintenance_operation_audit_info(
            operation,
            db_connection,
            schema_name,
            table_name,
            (
                "успешно завершено"
                if result["status"] == "completed"
                else "ошибка выполнения"
            ),
            result.get("message") if result["status"] == "failed" else None,
        )
    else:
        audit_info = "; ".join(
            [
                f"Действие: {MAINTENANCE_OPERATION_LABELS.get(operation, operation.upper())}",
                f"ID подключения: {connection_id}",
                f"Схема: {schema_name}",
                f"Таблица: {table_name}",
                "Результат: ошибка выполнения",
                f"Ошибка: {result['message']}",
            ]
        )
    _write_audit(operation, audit_info, username=username)
    close_old_connections()


def _require_payload_connection(request, payload):
    """Проверяет запрос и возвращает выбранное подключение."""
    connection_id = payload.get("id")
    if not connection_id:
        return None, JsonResponse(
            {"ok": False, "message": "Подключение не выбрано"}, status=400
        )
    return _get_connection_for_request(request, connection_id), None


def _greenplum_only_error():
    """Возвращает ошибку для функций распределённых СУБД."""
    return JsonResponse(
        {
            "ok": False,
            "message": "Эта функция доступна только для подключений типа Greenplum или Greengage",
        },
        status=400,
    )


def _require_greenplum_connection(request, payload):
    """Возвращает подключение Greenplum или совместимого с ним Greengage."""
    db_connection, error_response = _require_payload_connection(request, payload)
    if error_response:
        return None, error_response
    if not db_connection.is_greenplum_compatible:
        return None, _greenplum_only_error()
    return db_connection, None


def _format_role_timestamp(value):
    """Форматирует срок действия роли базы данных."""
    if value is None:
        return "Бессрочно"
    return (
        value.strftime("%Y-%m-%d %H:%M:%S")
        if hasattr(value, "strftime")
        else str(value)
    )


def _role_flag(value):
    """Преобразует логический признак роли в отображаемое значение."""
    return "Да" if value else "Нет"


def _favorite_filter(payload, db_user, db_connection, object_type, columns):
    """Возвращает безопасное SQL-условие и параметры для фильтра «Избранные»."""
    if not payload.get("favorites_only"):
        return "", []
    keys = list(
        DBFavorite.objects.filter(
            user=db_user, connection=db_connection, object_type=object_type
        ).values_list("object_key", flat=True)
    )
    values = [
        tuple(key.split("\x1f", len(columns) - 1)) if len(columns) > 1 else (key,)
        for key in keys
    ]
    values = [value for value in values if len(value) == len(columns)]
    if not values:
        return "AND FALSE", []
    clauses = [
        "(" + " AND ".join(f"{column} = %s" for column in columns) + ")"
        for _value in values
    ]
    return f"AND ({' OR '.join(clauses)})", [part for value in values for part in value]


def _database_roles_list(request, *, can_login):
    """Возвращает отфильтрованный список пользователей или групп базы данных."""
    payload = _read_json_body(request)
    db_connection, error_response = _require_payload_connection(request, payload)
    if error_response:
        return error_response
    page, page_size, offset, search, sort_column, direction = _list_query_params(
        payload,
        {
            "name": "name",
            "superuser": "superuser",
            "createdb": "createdb",
            "createrole": "createrole",
            "inherit": "inherit",
            "replication": "replication",
            "connection_limit": "connection_limit",
            "valid_until": "valid_until",
            "member_count": "member_count",
        },
        "name",
        default_page_size=100 if can_login else 10000,
    )
    role_type_message = "пользователей" if can_login else "групп"

    where_sql = ""
    params = [can_login]
    if search:
        search_sql, search_params = _multi_column_search_filter(
            search, ("role_info.rolname",)
        )
        where_sql = search_sql
        params.extend(search_params)
    favorite_sql, favorite_params = _favorite_filter(
        payload,
        _current_db_user(request),
        db_connection,
        "user" if can_login else "group",
        ("role_info.rolname",),
    )
    where_sql += f" {favorite_sql}"
    params.extend(favorite_params)

    roles_query = f"""
        WITH roles AS (
            SELECT
                role_info.rolname AS name,
                role_info.rolsuper AS superuser,
                role_info.rolcreatedb AS createdb,
                role_info.rolcreaterole AS createrole,
                role_info.rolinherit AS inherit,
                role_info.rolreplication AS replication,
                role_info.rolconnlimit AS connection_limit,
                role_info.rolvaliduntil AS valid_until,
                COUNT(membership.member)::bigint AS member_count
            FROM pg_catalog.pg_roles AS role_info
            LEFT JOIN pg_catalog.pg_auth_members AS membership
                ON membership.roleid = role_info.oid
            WHERE role_info.rolcanlogin = %s
              {where_sql}
            GROUP BY
                role_info.rolname,
                role_info.rolsuper,
                role_info.rolcreatedb,
                role_info.rolcreaterole,
                role_info.rolinherit,
                role_info.rolreplication,
                role_info.rolconnlimit,
                role_info.rolvaliduntil
        )
        SELECT
            name,
            superuser,
            createdb,
            createrole,
            inherit,
            replication,
            connection_limit,
            valid_until,
            member_count,
            COUNT(*) OVER() AS total_count,
            SUM(CASE WHEN superuser THEN 1 ELSE 0 END) OVER() AS superuser_count,
            SUM(CASE WHEN createdb THEN 1 ELSE 0 END) OVER() AS createdb_count,
            SUM(CASE WHEN replication THEN 1 ELSE 0 END) OVER() AS replication_count,
            SUM(CASE WHEN superuser OR createdb OR createrole OR replication THEN 1 ELSE 0 END) OVER() AS privileged_count
        FROM roles
        ORDER BY {sort_column} {direction}, name ASC
        LIMIT %s OFFSET %s;
    """

    try:
        rows = _fetch_db_rows(db_connection, roles_query, [*params, page_size, offset])
    except Exception as exc:
        return JsonResponse(
            {
                "ok": False,
                "message": _safe_db_error_message(
                    f"Не удалось получить список {role_type_message}", exc
                ),
            },
            status=400,
        )

    roles = [
        {
            "name": row[0],
            "superuser": _role_flag(row[1]),
            "createdb": _role_flag(row[2]),
            "createrole": _role_flag(row[3]),
            "inherit": _role_flag(row[4]),
            "replication": _role_flag(row[5]),
            "connection_limit": "Без лимита" if row[6] == -1 else str(row[6]),
            "valid_until": _format_role_timestamp(row[7]),
            "member_count": int(row[8] or 0),
        }
        for row in rows
    ]
    total_count = int(rows[0][9]) if rows else 0
    summary = {
        "total_count": total_count,
        "superuser_count": int(rows[0][10]) if rows else 0,
        "createdb_count": int(rows[0][11]) if rows else 0,
        "replication_count": int(rows[0][12]) if rows else 0,
        "privileged_count": int(rows[0][13]) if rows else 0,
    }
    return JsonResponse(
        {
            "ok": True,
            "roles": roles,
            "page": page,
            "page_size": page_size,
            "total_count": total_count,
            "summary": summary,
        }
    )
