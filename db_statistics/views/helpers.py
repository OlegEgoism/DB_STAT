"""Sidebar settings, user/connection serialization, and misc formatting helpers.

Connection pooling/queries live in views/pool.py, session/permission/rate-limit
checks in views/auth.py, audit-log writing in views/audit.py, list pagination/
search/favorites filtering in views/pagination.py, and background maintenance
jobs + backend termination in views/maintenance.py. Keeping this split makes
each concern independently readable instead of one ~900-line grab-bag.
"""

import json

from django.conf import settings
from django.http import JsonResponse

from db_statistics.models import DBUserSidebarSettings
from db_statistics.views.auth import _current_db_user, _require_payload_connection
from db_statistics.views.pagination import _favorite_filter, _list_query_params, _multi_column_search_filter
from db_statistics.views.pool import _fetch_db_rows, _query_or_error

# Служебные схемы, которые не показываются пользователю как обычные объекты БД.
EXCLUDED_SYSTEM_SCHEMAS_SQL = "('pg_catalog', 'information_schema', 'gp_toolkit')"


def _normalize_sidebar_tabs(tabs):
    """Проверяет и нормализует список вкладок бокового меню"""
    if not isinstance(tabs, list):
        return settings.SIDEBAR_TAB_IDS.copy()
    normalized_tabs = list(dict.fromkeys(tab for tab in tabs if tab in settings.SIDEBAR_TAB_IDS))
    if not any(tab not in settings.FIXED_SIDEBAR_TAB_IDS for tab in normalized_tabs):
        return settings.SIDEBAR_TAB_IDS.copy()
    normalized_tabs.extend(tab for tab in settings.SIDEBAR_TAB_IDS if tab in settings.FIXED_SIDEBAR_TAB_IDS and tab not in normalized_tabs)
    return normalized_tabs


def _normalize_sidebar_sections(sections):
    """Проверяет и нормализует порядок разделов бокового меню"""
    if not isinstance(sections, list):
        return settings.SIDEBAR_SECTION_IDS.copy()
    normalized_sections = list(dict.fromkeys(section for section in sections if section in settings.SIDEBAR_SECTION_IDS))
    normalized_sections.extend(section for section in settings.SIDEBAR_SECTION_IDS if section not in normalized_sections)
    return normalized_sections


def _sidebar_settings_values(sidebar_settings):
    """Извлекает нормализованные значения настроек бокового меню"""
    stored_value = sidebar_settings.visible_tabs
    if isinstance(stored_value, dict):
        return (_normalize_sidebar_tabs(stored_value.get("visible_tabs")), _normalize_sidebar_sections(stored_value.get("section_order")))
    return _normalize_sidebar_tabs(stored_value), settings.SIDEBAR_SECTION_IDS.copy()


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
    return [tab_id for tab_id in visible_tabs if tab_id in available_tabs], section_order


def _sidebar_settings_audit_info(db_user, visible_tabs, previous_tabs):
    """Формирует описание изменения настроек бокового меню для аудита"""
    visible_labels = ", ".join(_sidebar_tab_labels(visible_tabs))
    previous_labels = ", ".join(_sidebar_tab_labels(previous_tabs))
    return "Настройки сайдбара пользователя изменены: " f"Пользователь: {db_user.login}; " f"Отображаемые вкладки: {visible_labels}; " f"Предыдущие вкладки: {previous_labels}"


def _sidebar_settings_for_user(db_user):
    """Получает или создаёт настройки бокового меню пользователя"""
    sidebar_settings, _created = DBUserSidebarSettings.objects.get_or_create(user=db_user, defaults={"visible_tabs": settings.SIDEBAR_TAB_IDS.copy()})
    normalized_tabs, normalized_sections = _sidebar_settings_values(sidebar_settings)
    normalized_value = {"visible_tabs": normalized_tabs, "section_order": normalized_sections}
    if sidebar_settings.visible_tabs != normalized_value:
        sidebar_settings.visible_tabs = normalized_value
        sidebar_settings.save(update_fields=["visible_tabs", "updated"])
    return sidebar_settings


def _user_payload(db_user):
    """Формирует клиентские данные текущего пользователя"""
    if not db_user:
        return None
    sidebar_settings = _sidebar_settings_for_user(db_user)
    visible_tabs, section_order = _sidebar_settings_values_for_user(sidebar_settings, db_user)
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
    multipliers = {"b": 1, "byte": 1, "bytes": 1, "kb": 1024, "kib": 1024, "mb": 1024**2, "mib": 1024**2, "gb": 1024**3, "gib": 1024**3, "tb": 1024**4, "tib": 1024**4}
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


def _format_role_timestamp(value):
    """Форматирует срок действия роли базы данных."""
    if value is None:
        return "Бессрочно"
    return value.strftime("%Y-%m-%d %H:%M:%S") if hasattr(value, "strftime") else str(value)


def _role_flag(value):
    """Преобразует логический признак роли в отображаемое значение."""
    return "Да" if value else "Нет"


def _database_roles_list(request, *, can_login):
    """Возвращает отфильтрованный список пользователей или групп базы данных."""
    payload = _read_json_body(request)
    db_connection, error_response = _require_payload_connection(request, payload)
    if error_response:
        return error_response
    page, page_size, offset, search, sort_column, direction = _list_query_params(
        payload,
        {"name": "name", "superuser": "superuser", "createdb": "createdb", "createrole": "createrole", "inherit": "inherit", "replication": "replication", "connection_limit": "connection_limit", "valid_until": "valid_until", "member_count": "member_count"},
        "name",
        default_page_size=settings.PAGINATION_DEFAULT_PAGE_SIZE,
    )
    role_type_message = "пользователей" if can_login else "групп"

    where_sql = ""
    params = [can_login]
    if search:
        search_sql, search_params = _multi_column_search_filter(search, ("role_info.rolname",))
        where_sql = search_sql
        params.extend(search_params)
    favorite_sql, favorite_params = _favorite_filter(payload, _current_db_user(request), db_connection, "user" if can_login else "group", ("role_info.rolname",))
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

    rows, error_response = _query_or_error(f"Не удалось получить список {role_type_message}", lambda: _fetch_db_rows(db_connection, roles_query, [*params, page_size, offset]))
    if error_response:
        return error_response

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
    summary = {"total_count": total_count, "superuser_count": int(rows[0][10]) if rows else 0, "createdb_count": int(rows[0][11]) if rows else 0, "replication_count": int(rows[0][12]) if rows else 0, "privileged_count": int(rows[0][13]) if rows else 0}
    return JsonResponse({"ok": True, "roles": roles, "page": page, "page_size": page_size, "total_count": total_count, "summary": summary})
