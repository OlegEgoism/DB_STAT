"""Pagination, search, and favorites-filter helpers shared by the list views.

Split out of views/helpers.py (see its module docstring).
"""

from django.conf import settings
from django.db import OperationalError, ProgrammingError

from db_statistics.models import DBFavorite, DBPaginationSettings


def _pagination_page_sizes():
    """Возвращает размеры страниц из БД или безопасные значения первого запуска."""
    try:
        configured_sizes = list(DBPaginationSettings.objects.order_by("size").values_list("size", flat=True))
    except (OperationalError, ProgrammingError):
        configured_sizes = []
    return configured_sizes or list(settings.PAGINATION_PAGE_SIZE_OPTIONS)


def _list_query_params(payload, sort_columns, default_sort, *, default_page_size=None):
    """Разбирает общие параметры пагинации, поиска и сортировки для списковых запросов.

    Возвращает (page, page_size, offset, search, sort_column, direction).
    """
    if default_page_size is None:
        default_page_size = settings.PAGINATION_DEFAULT_PAGE_SIZE
    allowed_page_sizes = _pagination_page_sizes()
    if default_page_size != 10000 and default_page_size not in allowed_page_sizes:
        default_page_size = allowed_page_sizes[0]
    try:
        requested_page_size = int(payload.get("page_size") or default_page_size)
    except (TypeError, ValueError):
        requested_page_size = default_page_size
    page_size = requested_page_size if requested_page_size in allowed_page_sizes else default_page_size
    try:
        page = max(int(payload.get("page") or 1), 1)
    except (TypeError, ValueError, OverflowError):
        page = 1
    offset = (page - 1) * page_size
    search = str(payload.get("search") or "").strip()
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


def _favorite_filter(payload, db_user, db_connection, object_type, columns):
    """Возвращает безопасное SQL-условие и параметры для фильтра «Избранные»."""
    if not payload.get("favorites_only"):
        return "", []
    keys = list(DBFavorite.objects.filter(user=db_user, connection=db_connection, object_type=object_type).values_list("object_key", flat=True))
    values = [tuple(key.split("\x1f", len(columns) - 1)) if len(columns) > 1 else (key,) for key in keys]
    values = [value for value in values if len(value) == len(columns)]
    if not values:
        return "AND FALSE", []
    clauses = ["(" + " AND ".join(f"{column} = %s" for column in columns) + ")" for _value in values]
    return f"AND ({' OR '.join(clauses)})", [part for value in values for part in value]
