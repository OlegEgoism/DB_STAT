from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from psycopg2 import sql

from db_statistics.queries import data_sql
from db_statistics.views.audit import _connection_audit_fields, _format_audit_details, _write_audit
from db_statistics.views.auth import _current_db_user, _destructive_action_permission_error, _get_connection_for_request, _greenplum_only_error, _require_greenplum_connection, _require_payload_connection
from db_statistics.views.helpers import _format_bytes, _read_json_body
from db_statistics.views.pagination import _list_query_params, _multi_column_search_filter, _search_and_favorites_filter
from db_statistics.views.pool import _fetch_db_resultsets, _fetch_db_rows, _open_database_connection, _query_or_error

SCHEMA_SEARCH_COLUMNS = ("namespace.nspname",)
TABLE_SEARCH_COLUMNS = ("namespace.nspname", "table_class.relname", "(namespace.nspname || '.' || table_class.relname)")
VIEW_SEARCH_COLUMNS = ("namespace.nspname", "view_class.relname", "(namespace.nspname || '.' || view_class.relname)")
FUNCTION_SEARCH_COLUMNS = ("namespace.nspname", "procedure.proname", "pg_catalog.pg_get_function_result(procedure.oid)", "pg_catalog.pg_get_function_arguments(procedure.oid)")
TOAST_TABLE_SEARCH_COLUMNS = ("parent_namespace.nspname", "parent.relname", "toast.relname", "(parent_namespace.nspname || '.' || parent.relname)")
TEMP_TABLE_SEARCH_COLUMNS = ("namespace.nspname", "table_class.relname", "(namespace.nspname || '.' || table_class.relname)")


@require_http_methods(["POST"])
def database_schema_sizes(request):
    """Возвращает размеры и статистику схем базы данных."""
    payload = _read_json_body(request)
    db_connection, error_response = _require_payload_connection(request, payload)
    if error_response:
        return error_response
    page, page_size, offset, search, sort_column, direction = _list_query_params(payload, {"schema_name": "schema_name", "schema_owner": "schema_owner", "table_count": "table_count", "size_bytes": "size_bytes"}, "size_bytes")

    where_sql, params = _search_and_favorites_filter(request, payload, db_connection, search, SCHEMA_SEARCH_COLUMNS, "schema", ("namespace.nspname",))

    schema_sizes_query = data_sql.schema_sizes_sql(direction=direction, sort_column=sort_column, where_sql=where_sql)

    schema_distribution_query = data_sql.schema_distribution_sql(where_sql=where_sql)

    result, error_response = _query_or_error("Не удалось получить размеры схем", lambda: _fetch_db_resultsets(db_connection, (schema_sizes_query, [*params, page_size, offset]), (schema_distribution_query, params)))
    if error_response:
        return error_response
    rows, distribution_rows = result

    schemas = [{"schema_name": row[0], "schema_owner": row[1], "table_count": int(row[2]), "size_bytes": int(row[3]), "table_size": row[4]} for row in rows]
    schema_distribution = [{"schema_name": row[0], "size_bytes": int(row[1] or 0), "table_size": row[2]} for row in distribution_rows]
    total_count = int(rows[0][5]) if rows else len(schema_distribution)
    return JsonResponse({"ok": True, "schemas": schemas, "schema_distribution": schema_distribution, "page": page, "page_size": page_size, "total_count": total_count})


@require_http_methods(["POST"])
def database_table_sizes(request):
    """Возвращает размеры и статистику таблиц базы данных."""
    payload = _read_json_body(request)
    db_connection, error_response = _require_payload_connection(request, payload)
    if error_response:
        return error_response
    page, page_size, offset, search, sort_column, direction = _list_query_params(
        payload, {"schema_name": "schema_name", "table_name": "table_name", "table_owner": "table_owner", "size_bytes": "size_bytes", "index_size_bytes": "index_size_bytes", "index_count": "index_count", "row_count": "row_count"}, "size_bytes"
    )

    where_sql, params = _search_and_favorites_filter(request, payload, db_connection, search, TABLE_SEARCH_COLUMNS, "table", ("namespace.nspname", "table_class.relname"))

    table_sizes_query = data_sql.table_sizes_sql(direction=direction, sort_column=sort_column, where_sql=where_sql)

    table_distribution_query = data_sql.table_distribution_sql(where_sql=where_sql)

    result, error_response = _query_or_error("Не удалось получить размеры таблиц", lambda: _fetch_db_resultsets(db_connection, (table_sizes_query, [*params, page_size, offset]), (table_distribution_query, params)))
    if error_response:
        return error_response
    rows, distribution_rows = result

    tables = [{"schema_name": row[0], "table_name": row[1], "table_owner": row[2], "size_bytes": int(row[3]), "table_size": row[4], "index_size_bytes": int(row[5]), "index_size": row[6], "index_count": int(row[7]), "row_count": int(row[8])} for row in rows]
    table_distribution = [{"schema_name": row[0], "table_name": row[1], "size_bytes": int(row[2] or 0), "table_size": row[3]} for row in distribution_rows]
    total_count = int(rows[0][9]) if rows else len(table_distribution)
    return JsonResponse({"ok": True, "tables": tables, "table_distribution": table_distribution, "page": page, "page_size": page_size, "total_count": total_count})


@require_http_methods(["POST"])
def database_views_list(request):
    """Возвращает список обычных и материализованных представлений."""
    payload = _read_json_body(request)
    db_connection, error_response = _require_payload_connection(request, payload)
    if error_response:
        return error_response
    page, page_size, offset, search, sort_column, direction = _list_query_params(
        payload, {"schema_name": "schema_name", "view_name": "view_name", "view_owner": "view_owner", "view_type": "view_type", "size_bytes": "size_bytes", "index_size_bytes": "index_size_bytes", "row_count": "row_count"}, "schema_name"
    )
    view_type = payload.get("view_type") or ""

    where_sql = ""
    params = []
    type_sql = ""
    if view_type == "ordinary":
        type_sql = "AND view_class.relkind = 'v'"
    elif view_type == "materialized":
        type_sql = "AND view_class.relkind = 'm'"
    where_sql, params = _search_and_favorites_filter(request, payload, db_connection, search, VIEW_SEARCH_COLUMNS, "view", ("namespace.nspname", "view_class.relname"))

    views_query = data_sql.views_sql(direction=direction, sort_column=sort_column, type_sql=type_sql, where_sql=where_sql)

    rows, error_response = _query_or_error("Не удалось получить представления", lambda: _fetch_db_rows(db_connection, views_query, [*params, page_size, offset]))
    if error_response:
        return error_response

    items = [{"schema_name": row[0], "view_name": row[1], "view_owner": row[2], "view_type": row[3], "size_bytes": int(row[4]), "view_size": row[5], "index_size_bytes": int(row[6]), "index_size": row[7], "row_count": int(row[8])} for row in rows]
    total_count = int(rows[0][9]) if rows else 0
    materialized_count = int(rows[0][10]) if rows else 0
    ordinary_count = int(rows[0][11]) if rows else 0
    materialized_size_bytes = int(rows[0][12]) if rows else 0
    summary = {"materialized_count": materialized_count, "ordinary_count": ordinary_count, "materialized_size_bytes": materialized_size_bytes, "materialized_size": _format_bytes(materialized_size_bytes)}
    return JsonResponse({"ok": True, "views": items, "summary": summary, "page": page, "page_size": page_size, "total_count": total_count})


@require_http_methods(["POST"])
def database_functions_list(request):
    """Возвращает список функций базы данных и их сигнатуры."""
    payload = _read_json_body(request)
    db_connection, error_response = _require_payload_connection(request, payload)
    if error_response:
        return error_response

    page, page_size, offset, search, sort_column, direction = _list_query_params(payload, {"schema_name": "schema_name", "function_name": "function_name", "return_type": "return_type", "arguments": "arguments"}, "schema_name")

    where_sql, params = _search_and_favorites_filter(request, payload, db_connection, search, FUNCTION_SEARCH_COLUMNS, "function", ("namespace.nspname", "procedure.proname", "pg_catalog.pg_get_function_arguments(procedure.oid)"))

    functions_query = data_sql.functions_sql(direction=direction, sort_column=sort_column, where_sql=where_sql)

    rows, error_response = _query_or_error("Не удалось получить функции", lambda: _fetch_db_rows(db_connection, functions_query, [*params, page_size, offset]))
    if error_response:
        return error_response

    functions = [{"schema_name": row[0], "function_name": row[1], "return_type": row[2], "arguments": row[3]} for row in rows]
    total_count = int(rows[0][4]) if rows else 0
    return JsonResponse({"ok": True, "functions": functions, "page": page, "page_size": page_size, "total_count": total_count})


@require_http_methods(["POST"])
def distribution_tables(request):
    """Возвращает таблицы, доступные для анализа распределения."""
    payload = _read_json_body(request)
    db_connection, error_response = _require_greenplum_connection(request, payload)
    if error_response:
        return error_response
    tables_query = data_sql.tables_sql()

    rows, error_response = _query_or_error("Не удалось получить список таблиц", lambda: _fetch_db_rows(db_connection, tables_query))
    if error_response:
        return error_response

    tables = [{"schema_name": row[0], "table_name": row[1], "object_type": row[2]} for row in rows]
    return JsonResponse({"ok": True, "tables": tables})


@require_http_methods(["POST"])
def distribution_info(request):
    """Возвращает распределение строк таблицы по сегментам."""
    payload = _read_json_body(request)
    connection_id = payload.get("id")
    schema_name = (payload.get("schema_name") or "").strip()
    table_name = (payload.get("table_name") or "").strip()
    if not connection_id:
        return JsonResponse({"ok": False, "message": "Подключение не выбрано"}, status=400)
    if not schema_name or not table_name:
        return JsonResponse({"ok": False, "message": "Таблица не выбрана"}, status=400)

    db_connection = _get_connection_for_request(request, connection_id)
    if not db_connection.is_greenplum_compatible:
        return _greenplum_only_error()
    validate_query = data_sql.VALIDATE_SQL
    distribution_query = data_sql.segment_distribution_sql(schema_name, table_name)

    def _fetch_distribution_rows():
        with _open_database_connection(db_connection) as connection:
            with connection.cursor() as cursor:
                cursor.execute(validate_query, [schema_name, table_name])
                if not cursor.fetchone():
                    return None
                cursor.execute(distribution_query)
                return cursor.fetchall()

    rows, error_response = _query_or_error("Не удалось получить распределение", _fetch_distribution_rows)
    if error_response:
        return error_response
    if rows is None:
        return JsonResponse({"ok": False, "message": "Выбранная таблица не найдена"}, status=404)

    segments = [{"segment_id": int(row[0]), "row_count": int(row[1])} for row in rows]
    counts = [item["row_count"] for item in segments]
    total_rows = sum(counts)
    used_segments = sum(1 for count in counts if count > 0)
    min_rows = min(counts) if counts else 0
    max_rows = max(counts) if counts else 0
    avg_rows = round(total_rows / len(counts), 2) if counts else 0
    skew_ratio = round(max_rows / min_rows, 2) if min_rows else (float(max_rows) if max_rows else 0)
    status = "высокий" if skew_ratio >= 1.5 else "средний" if skew_ratio >= 1.2 else "норм."

    return JsonResponse(
        {"ok": True, "schema_name": schema_name, "table_name": table_name, "segments": segments, "metrics": {"total_rows": total_rows, "used_segments": used_segments, "min_rows": min_rows, "max_rows": max_rows, "avg_rows": avg_rows, "skew_ratio": skew_ratio, "status": status}}
    )


@require_http_methods(["POST"])
def database_temp_table_sizes(request):
    """Возвращает размеры активных временных таблиц."""
    payload = _read_json_body(request)
    db_connection, error_response = _require_payload_connection(request, payload)
    if error_response:
        return error_response
    page, page_size, offset, search, sort_column, direction = _list_query_params(payload, {"schema_name": "schema_name", "table_name": "table_name", "table_owner": "table_owner", "size_bytes": "size_bytes", "session_label": "session_label"}, "size_bytes")

    where_sql = ""
    params = []
    if search:
        where_sql, params = _multi_column_search_filter(search, TEMP_TABLE_SEARCH_COLUMNS)

    temp_table_sizes_query = data_sql.temp_table_sizes_sql(direction=direction, sort_column=sort_column, where_sql=where_sql)

    temp_table_distribution_query = data_sql.temp_table_distribution_sql(where_sql=where_sql)

    result, error_response = _query_or_error("Не удалось получить временные таблицы", lambda: _fetch_db_resultsets(db_connection, (temp_table_sizes_query, [*params, page_size, offset]), (temp_table_distribution_query, params)))
    if error_response:
        return error_response
    rows, distribution_rows = result

    temp_tables = [{"schema_name": row[0], "table_name": row[1], "table_owner": row[2], "size_bytes": int(row[3]), "table_size": row[4], "session_label": row[5]} for row in rows]
    temp_table_distribution = [{"schema_name": row[0], "table_name": row[1], "size_bytes": int(row[2] or 0), "table_size": row[3]} for row in distribution_rows]
    total_count = int(rows[0][6]) if rows else len(temp_table_distribution)
    return JsonResponse({"ok": True, "temp_tables": temp_tables, "temp_table_distribution": temp_table_distribution, "page": page, "page_size": page_size, "total_count": total_count})


@require_http_methods(["POST"])
def database_toast_table_sizes(request):
    """Возвращает TOAST-таблицы с данными: размер, доля от таблицы-владельца и мёртвые версии строк."""
    payload = _read_json_body(request)
    db_connection, error_response = _require_payload_connection(request, payload)
    if error_response:
        return error_response
    page, page_size, offset, search, sort_column, direction = _list_query_params(
        payload, {"schema_name": "schema_name", "table_name": "table_name", "toast_table_name": "toast_table_name", "toast_total_bytes": "toast_total_bytes", "heap_bytes": "heap_bytes", "toast_share": "toast_share", "dead_chunks": "dead_chunks"}, "toast_total_bytes"
    )

    # Избранное общее с вкладкой «Таблицы»: ключ — таблица-владелец (схема + имя), а не TOAST-таблица.
    where_sql, params = _search_and_favorites_filter(request, payload, db_connection, search, TOAST_TABLE_SEARCH_COLUMNS, "table", ("parent_namespace.nspname", "parent.relname"))

    toast_tables_query = data_sql.toast_tables_sql(direction=direction, sort_column=sort_column, where_sql=where_sql)

    rows, error_response = _query_or_error("Не удалось получить TOAST-таблицы", lambda: _fetch_db_rows(db_connection, toast_tables_query, [*params, page_size, offset]))
    if error_response:
        return error_response

    toast_tables = [
        {
            "schema_name": row[0],
            "table_name": row[1],
            "toast_table_name": row[2],
            "toast_bytes": int(row[3]),
            "toast_index_bytes": int(row[4]),
            "toast_total_bytes": int(row[5]),
            "toast_total_size": row[6],
            "heap_size": row[7],
            "heap_bytes": int(row[8]),
            "toast_share": float(row[9]),
            "live_chunks": int(row[10]),
            "dead_chunks": int(row[11]),
        }
        for row in rows
    ]
    total_count = int(rows[0][12]) if rows else 0
    all_toast_size = rows[0][14] if rows else "0 bytes"
    return JsonResponse({"ok": True, "toast_tables": toast_tables, "page": page, "page_size": page_size, "total_count": total_count, "all_toast_size": all_toast_size})


@require_http_methods(["POST"])
def delete_temp_table(request):
    """Удаляет выбранную временную таблицу в целевой базе данных."""
    permission_error = _destructive_action_permission_error(request)
    if permission_error:
        return permission_error

    payload = _read_json_body(request)
    db_connection, error_response = _require_payload_connection(request, payload)
    if error_response:
        return error_response

    schema_name = str(payload.get("schema_name") or "").strip()
    table_name = str(payload.get("table_name") or "").strip()
    if not schema_name or not table_name:
        return JsonResponse({"ok": False, "message": "Укажите схему и имя временной таблицы"}, status=400)

    def drop_table():
        with _open_database_connection(db_connection) as connection:
            with connection.cursor() as cursor:
                cursor.execute(data_sql.TEMP_TABLE_EXISTS_SQL, [schema_name, table_name])
                if cursor.fetchone() is None:
                    return False
                cursor.execute(sql.SQL("DROP TABLE {}.{}").format(sql.Identifier(schema_name), sql.Identifier(table_name)))
            connection.commit()
        return True

    deleted, error_response = _query_or_error("Не удалось удалить временную таблицу", drop_table)
    if error_response:
        return error_response
    if not deleted:
        return JsonResponse({"ok": False, "message": "Временная таблица не найдена"}, status=404)

    _write_audit(
        "temp_table_delete", _format_audit_details([("Действие", "Удаление временной таблицы"), *_connection_audit_fields(db_connection, server_label=True), ("Схема", schema_name), ("Таблица", table_name), ("Результат", "успешно удалена")]), db_user=_current_db_user(request)
    )
    return JsonResponse({"ok": True, "message": f"Временная таблица {schema_name}.{table_name} удалена", "schema_name": schema_name, "table_name": table_name})
