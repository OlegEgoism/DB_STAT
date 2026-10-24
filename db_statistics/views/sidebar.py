"""Настройки бокового меню пользователя: вкладки, порядок разделов и клиентские данные пользователя.

Модуль зависит только от настроек
Django и модели DBUserSidebarSettings, поэтому его можно импортировать из любого view-модуля.
"""

from django.conf import settings

from db_statistics.models import DBUserSidebarSettings


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
