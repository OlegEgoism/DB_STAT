"""Sidebar settings, user/connection serialization, and misc formatting helpers.

Connection pooling/queries live in views/pool.py, session/permission/rate-limit
checks in views/auth.py, audit-log writing in views/audit.py, list pagination/
search/favorites filtering in views/pagination.py, and background maintenance
jobs + backend termination in views/maintenance.py. Keeping this split makes
each concern independently readable instead of one ~900-line grab-bag.
"""

import json

from django.conf import settings

from db_statistics.models import DBUserSidebarSettings

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


def _add_new_sidebar_tabs(visible_tabs, known_tabs):
    """Добавляет вкладки, появившиеся после сохранения настроек, рядом с соседней по порядку вкладкой.

    known_tabs — вкладки, которые пользователь уже видел при последнем сохранении; всё, что
    он скрыл из известных, остаётся скрытым. Если поля нет (старые настройки), новыми
    считаются вкладки из SIDEBAR_TABS_ADDED_LATER.
    """
    if isinstance(known_tabs, list):
        known = set(known_tabs)
    else:
        known = set(settings.SIDEBAR_TAB_IDS) - settings.SIDEBAR_TABS_ADDED_LATER
    result = list(visible_tabs)
    for index, tab_id in enumerate(settings.SIDEBAR_TAB_IDS):
        if tab_id in known or tab_id in result:
            continue
        previous_tabs = [tab for tab in settings.SIDEBAR_TAB_IDS[:index] if tab in result]
        position = result.index(previous_tabs[-1]) + 1 if previous_tabs else 0
        result.insert(position, tab_id)
    return result


def _sidebar_settings_values(sidebar_settings):
    """Извлекает нормализованные значения настроек бокового меню"""
    stored_value = sidebar_settings.visible_tabs
    if isinstance(stored_value, dict):
        visible_tabs = _add_new_sidebar_tabs(_normalize_sidebar_tabs(stored_value.get("visible_tabs")), stored_value.get("known_tabs"))
        return visible_tabs, _normalize_sidebar_sections(stored_value.get("section_order"))
    return _add_new_sidebar_tabs(_normalize_sidebar_tabs(stored_value), None), settings.SIDEBAR_SECTION_IDS.copy()


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
    return f"Настройки сайдбара пользователя изменены: Пользователь: {db_user.login}; Отображаемые вкладки: {visible_labels}; Предыдущие вкладки: {previous_labels}"


def _sidebar_settings_for_user(db_user):
    """Получает или создаёт настройки бокового меню пользователя"""
    sidebar_settings, _created = DBUserSidebarSettings.objects.get_or_create(user=db_user, defaults={"visible_tabs": settings.SIDEBAR_TAB_IDS.copy()})
    normalized_tabs, normalized_sections = _sidebar_settings_values(sidebar_settings)
    normalized_value = {"visible_tabs": normalized_tabs, "section_order": normalized_sections, "known_tabs": settings.SIDEBAR_TAB_IDS.copy()}
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
