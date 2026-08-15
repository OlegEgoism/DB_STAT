from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from psycopg2 import sql

from db_statistics.view_helpers import (
    EXCLUDED_SYSTEM_SCHEMAS_SQL,
    _current_db_user,
    _favorite_filter,
    _fetch_db_resultsets,
    _fetch_db_rows,
    _format_bytes,
    _get_connection_for_request,
    _greenplum_only_error,
    _list_query_params,
    _multi_column_search_filter,
    _open_database_connection,
    _read_json_body,
    _require_greenplum_connection,
    _require_payload_connection,
    _safe_db_error_message,
)


@require_http_methods(["POST"])
def database_schema_sizes(request):
    """Возвращает размеры и статистику схем базы данных."""
    payload = _read_json_body(request)
    db_connection, error_response = _require_payload_connection(request, payload)
    if error_response:
        return error_response
    page, page_size, offset, search, sort_column, direction = _list_query_params(
        payload,
        {
            "schema_name": "schema_name",
            "schema_owner": "schema_owner",
            "table_count": "table_count",
            "size_bytes": "size_bytes",
        },
        "size_bytes",
    )

    where_sql = ""
    params = []
    if search:
        where_sql, search_params = _multi_column_search_filter(
            search, ("namespace.nspname", "owner.rolname")
        )
        params.extend(search_params)
    favorite_sql, favorite_params = _favorite_filter(
        payload,
        _current_db_user(request),
        db_connection,
        "schema",
        ("namespace.nspname",),
    )
    where_sql += f" {favorite_sql}"
    params.extend(favorite_params)

    schema_sizes_query = f"""
        WITH schema_sizes AS (
            SELECT
                namespace.nspname AS schema_name,
                COALESCE(owner.rolname, '-') AS schema_owner,
                COUNT(table_class.oid)::bigint AS table_count,
                SUM(pg_total_relation_size(table_class.oid))::bigint AS size_bytes
            FROM pg_catalog.pg_class AS table_class
            JOIN pg_catalog.pg_namespace AS namespace
                ON namespace.oid = table_class.relnamespace
            LEFT JOIN pg_catalog.pg_roles AS owner
                ON owner.oid = namespace.nspowner
            WHERE table_class.relkind IN ('r', 'p', 'm')
              AND namespace.nspname NOT IN {EXCLUDED_SYSTEM_SCHEMAS_SQL}
              AND namespace.nspname NOT LIKE 'pg_toast%%'
              {where_sql}
            GROUP BY namespace.nspname, owner.rolname
        )
        SELECT
            schema_name,
            schema_owner,
            table_count,
            size_bytes,
            pg_size_pretty(size_bytes) AS table_size,
            COUNT(*) OVER() AS total_count
        FROM schema_sizes
        ORDER BY {sort_column} {direction}, schema_name ASC
        LIMIT %s OFFSET %s;
    """

    schema_distribution_query = f"""
        WITH schema_sizes AS (
            SELECT
                namespace.nspname AS schema_name,
                SUM(pg_total_relation_size(table_class.oid))::bigint AS size_bytes
            FROM pg_catalog.pg_class AS table_class
            JOIN pg_catalog.pg_namespace AS namespace
                ON namespace.oid = table_class.relnamespace
            LEFT JOIN pg_catalog.pg_roles AS owner
                ON owner.oid = namespace.nspowner
            WHERE table_class.relkind IN ('r', 'p', 'm')
              AND namespace.nspname NOT IN {EXCLUDED_SYSTEM_SCHEMAS_SQL}
              AND namespace.nspname NOT LIKE 'pg_toast%%'
              {where_sql}
            GROUP BY namespace.nspname
        )
        SELECT
            schema_name,
            size_bytes,
            pg_size_pretty(size_bytes) AS table_size
        FROM schema_sizes
        ORDER BY size_bytes DESC, schema_name ASC;
    """

    try:
        rows, distribution_rows = _fetch_db_resultsets(
            db_connection,
            (schema_sizes_query, [*params, page_size, offset]),
            (schema_distribution_query, params),
        )
    except Exception as exc:
        return JsonResponse(
            {
                "ok": False,
                "message": _safe_db_error_message("Не удалось получить размеры схем", exc),
            },
            status=400,
        )

    schemas = [
        {
            "schema_name": row[0],
            "schema_owner": row[1],
            "table_count": int(row[2]),
            "size_bytes": int(row[3]),
            "table_size": row[4],
        }
        for row in rows
    ]
    schema_distribution = [
        {"schema_name": row[0], "size_bytes": int(row[1] or 0), "table_size": row[2]}
        for row in distribution_rows
    ]
    total_count = int(rows[0][5]) if rows else len(schema_distribution)
    return JsonResponse(
        {
            "ok": True,
            "schemas": schemas,
            "schema_distribution": schema_distribution,
            "page": page,
            "page_size": page_size,
            "total_count": total_count,
        }
    )


@require_http_methods(["POST"])
def database_table_sizes(request):
    """Возвращает размеры и статистику таблиц базы данных."""
    payload = _read_json_body(request)
    db_connection, error_response = _require_payload_connection(request, payload)
    if error_response:
        return error_response
    page, page_size, offset, search, sort_column, direction = _list_query_params(
        payload,
        {
            "schema_name": "schema_name",
            "table_name": "table_name",
            "table_owner": "table_owner",
            "size_bytes": "size_bytes",
            "index_size_bytes": "index_size_bytes",
            "index_count": "index_count",
            "row_count": "row_count",
        },
        "size_bytes",
    )

    where_sql = ""
    params = []
    if search:
        where_sql, search_params = _multi_column_search_filter(
            search,
            (
                "namespace.nspname",
                "table_class.relname",
                "(namespace.nspname || '.' || table_class.relname)",
                "owner.rolname",
            ),
        )
        params.extend(search_params)
    favorite_sql, favorite_params = _favorite_filter(
        payload,
        _current_db_user(request),
        db_connection,
        "table",
        ("namespace.nspname", "table_class.relname"),
    )
    where_sql += f" {favorite_sql}"
    params.extend(favorite_params)

    table_sizes_query = f"""
        WITH table_sizes AS (
            SELECT
                namespace.nspname AS schema_name,
                table_class.relname AS table_name,
                COALESCE(owner.rolname, '-') AS table_owner,
                pg_total_relation_size(table_class.oid)::bigint AS size_bytes,
                pg_indexes_size(table_class.oid)::bigint AS index_size_bytes,
                (
                    SELECT COUNT(*)::bigint
                    FROM pg_catalog.pg_index AS index_info
                    WHERE index_info.indrelid = table_class.oid
                ) AS index_count,
                GREATEST(table_class.reltuples::bigint, 0) AS row_count
            FROM pg_catalog.pg_class AS table_class
            JOIN pg_catalog.pg_namespace AS namespace
                ON namespace.oid = table_class.relnamespace
            LEFT JOIN pg_catalog.pg_roles AS owner
                ON owner.oid = table_class.relowner
            WHERE table_class.relkind IN ('r', 'p')
              AND namespace.nspname NOT IN {EXCLUDED_SYSTEM_SCHEMAS_SQL}
              AND namespace.nspname NOT LIKE 'pg_toast%%'
              {where_sql}
        )
        SELECT
            schema_name,
            table_name,
            table_owner,
            size_bytes,
            pg_size_pretty(size_bytes) AS table_size,
            index_size_bytes,
            pg_size_pretty(index_size_bytes) AS index_size,
            index_count,
            row_count,
            COUNT(*) OVER() AS total_count
        FROM table_sizes
        ORDER BY {sort_column} {direction}, schema_name ASC, table_name ASC
        LIMIT %s OFFSET %s;
    """

    table_distribution_query = f"""
        WITH table_sizes AS (
            SELECT
                namespace.nspname AS schema_name,
                table_class.relname AS table_name,
                pg_total_relation_size(table_class.oid)::bigint AS size_bytes
            FROM pg_catalog.pg_class AS table_class
            JOIN pg_catalog.pg_namespace AS namespace
                ON namespace.oid = table_class.relnamespace
            WHERE table_class.relkind IN ('r', 'p')
              AND namespace.nspname NOT IN {EXCLUDED_SYSTEM_SCHEMAS_SQL}
              AND namespace.nspname NOT LIKE 'pg_toast%%'
              {where_sql}
        )
        SELECT
            schema_name,
            table_name,
            size_bytes,
            pg_size_pretty(size_bytes) AS table_size
        FROM table_sizes
        ORDER BY size_bytes DESC, schema_name ASC, table_name ASC;
    """

    try:
        rows, distribution_rows = _fetch_db_resultsets(
            db_connection,
            (table_sizes_query, [*params, page_size, offset]),
            (table_distribution_query, params),
        )
    except Exception as exc:
        return JsonResponse(
            {
                "ok": False,
                "message": _safe_db_error_message("Не удалось получить размеры таблиц", exc),
            },
            status=400,
        )

    tables = [
        {
            "schema_name": row[0],
            "table_name": row[1],
            "table_owner": row[2],
            "size_bytes": int(row[3]),
            "table_size": row[4],
            "index_size_bytes": int(row[5]),
            "index_size": row[6],
            "index_count": int(row[7]),
            "row_count": int(row[8]),
        }
        for row in rows
    ]
    table_distribution = [
        {
            "schema_name": row[0],
            "table_name": row[1],
            "size_bytes": int(row[2] or 0),
            "table_size": row[3],
        }
        for row in distribution_rows
    ]
    total_count = int(rows[0][9]) if rows else len(table_distribution)
    return JsonResponse(
        {
            "ok": True,
            "tables": tables,
            "table_distribution": table_distribution,
            "page": page,
            "page_size": page_size,
            "total_count": total_count,
        }
    )


@require_http_methods(["POST"])
def database_views_list(request):
    """Возвращает список обычных и материализованных представлений."""
    payload = _read_json_body(request)
    db_connection, error_response = _require_payload_connection(request, payload)
    if error_response:
        return error_response
    page, page_size, offset, search, sort_column, direction = _list_query_params(
        payload,
        {
            "schema_name": "schema_name",
            "view_name": "view_name",
            "view_owner": "view_owner",
            "view_type": "view_type",
            "size_bytes": "size_bytes",
            "index_size_bytes": "index_size_bytes",
            "row_count": "row_count",
        },
        "schema_name",
    )
    view_type = payload.get("view_type") or ""

    where_sql = ""
    params = []
    type_sql = ""
    if view_type == "ordinary":
        type_sql = "AND view_class.relkind = 'v'"
    elif view_type == "materialized":
        type_sql = "AND view_class.relkind = 'm'"
    if search:
        where_sql, search_params = _multi_column_search_filter(
            search,
            (
                "namespace.nspname",
                "view_class.relname",
                "owner.rolname",
                "(namespace.nspname || '.' || view_class.relname)",
            ),
        )
        params.extend(search_params)
    favorite_sql, favorite_params = _favorite_filter(
        payload,
        _current_db_user(request),
        db_connection,
        "view",
        ("namespace.nspname", "view_class.relname"),
    )
    where_sql += f" {favorite_sql}"
    params.extend(favorite_params)

    views_query = f"""
        WITH database_views AS (
            SELECT
                namespace.nspname AS schema_name,
                view_class.relname AS view_name,
                COALESCE(owner.rolname, '-') AS view_owner,
                CASE view_class.relkind
                    WHEN 'm' THEN 'Материализованное'
                    ELSE 'Обычное'
                END AS view_type,
                CASE WHEN view_class.relkind = 'm' THEN pg_total_relation_size(view_class.oid)::bigint ELSE 0::bigint END AS size_bytes,
                CASE WHEN view_class.relkind = 'm' THEN pg_indexes_size(view_class.oid)::bigint ELSE 0::bigint END AS index_size_bytes,
                CASE WHEN view_class.relkind = 'm' THEN GREATEST(view_class.reltuples::bigint, 0) ELSE 0::bigint END AS row_count
            FROM pg_catalog.pg_class AS view_class
            JOIN pg_catalog.pg_namespace AS namespace
                ON namespace.oid = view_class.relnamespace
            LEFT JOIN pg_catalog.pg_roles AS owner
                ON owner.oid = view_class.relowner
            WHERE view_class.relkind IN ('v', 'm')
              AND namespace.nspname NOT IN {EXCLUDED_SYSTEM_SCHEMAS_SQL}
              AND namespace.nspname NOT LIKE 'pg_toast%%'
              {type_sql}
              {where_sql}
        )
        SELECT
            schema_name,
            view_name,
            view_owner,
            view_type,
            size_bytes,
            pg_size_pretty(size_bytes) AS view_size,
            index_size_bytes,
            pg_size_pretty(index_size_bytes) AS index_size,
            row_count,
            COUNT(*) OVER() AS total_count,
            COUNT(*) FILTER (WHERE view_type = 'Материализованное') OVER() AS materialized_count,
            COUNT(*) FILTER (WHERE view_type = 'Обычное') OVER() AS ordinary_count,
            COALESCE(SUM(size_bytes) FILTER (WHERE view_type = 'Материализованное') OVER(), 0)::bigint AS materialized_size_bytes
        FROM database_views
        ORDER BY {sort_column} {direction}, schema_name ASC, view_name ASC
        LIMIT %s OFFSET %s;
    """

    try:
        rows = _fetch_db_rows(db_connection, views_query, [*params, page_size, offset])
    except Exception as exc:
        return JsonResponse(
            {
                "ok": False,
                "message": _safe_db_error_message("Не удалось получить представления", exc),
            },
            status=400,
        )

    items = [
        {
            "schema_name": row[0],
            "view_name": row[1],
            "view_owner": row[2],
            "view_type": row[3],
            "size_bytes": int(row[4]),
            "view_size": row[5],
            "index_size_bytes": int(row[6]),
            "index_size": row[7],
            "row_count": int(row[8]),
        }
        for row in rows
    ]
    total_count = int(rows[0][9]) if rows else 0
    materialized_count = int(rows[0][10]) if rows else 0
    ordinary_count = int(rows[0][11]) if rows else 0
    materialized_size_bytes = int(rows[0][12]) if rows else 0
    summary = {
        "materialized_count": materialized_count,
        "ordinary_count": ordinary_count,
        "materialized_size_bytes": materialized_size_bytes,
        "materialized_size": _format_bytes(materialized_size_bytes),
    }
    return JsonResponse(
        {
            "ok": True,
            "views": items,
            "summary": summary,
            "page": page,
            "page_size": page_size,
            "total_count": total_count,
        }
    )


@require_http_methods(["POST"])
def database_functions_list(request):
    """Возвращает список функций базы данных и их сигнатуры."""
    payload = _read_json_body(request)
    db_connection, error_response = _require_payload_connection(request, payload)
    if error_response:
        return error_response

    page, page_size, offset, search, sort_column, direction = _list_query_params(
        payload,
        {
            "schema_name": "schema_name",
            "function_name": "function_name",
            "return_type": "return_type",
            "arguments": "arguments",
        },
        "schema_name",
    )

    where_sql = ""
    params = []
    if search:
        where_sql, params = _multi_column_search_filter(search, ("procedure.proname",))
    favorite_sql, favorite_params = _favorite_filter(
        payload,
        _current_db_user(request),
        db_connection,
        "function",
        (
            "namespace.nspname",
            "procedure.proname",
            "pg_catalog.pg_get_function_arguments(procedure.oid)",
        ),
    )
    where_sql += f" {favorite_sql}"
    params.extend(favorite_params)

    functions_query = f"""
        WITH database_functions AS (
            SELECT
                namespace.nspname AS schema_name,
                procedure.proname AS function_name,
                pg_catalog.pg_get_function_result(procedure.oid) AS return_type,
                pg_catalog.pg_get_function_arguments(procedure.oid) AS arguments
            FROM pg_catalog.pg_proc AS procedure
            JOIN pg_catalog.pg_namespace AS namespace
                ON namespace.oid = procedure.pronamespace
            WHERE namespace.nspname NOT IN {EXCLUDED_SYSTEM_SCHEMAS_SQL}
              AND namespace.nspname NOT LIKE 'pg_toast%%'
              {where_sql}
        )
        SELECT schema_name, function_name, return_type, arguments, COUNT(*) OVER() AS total_count
        FROM database_functions
        ORDER BY {sort_column} {direction}, schema_name ASC, function_name ASC, arguments ASC
        LIMIT %s OFFSET %s;
    """

    try:
        rows = _fetch_db_rows(
            db_connection, functions_query, [*params, page_size, offset]
        )
    except Exception as exc:
        return JsonResponse(
            {
                "ok": False,
                "message": _safe_db_error_message("Не удалось получить функции", exc),
            },
            status=400,
        )

    functions = [
        {
            "schema_name": row[0],
            "function_name": row[1],
            "return_type": row[2],
            "arguments": row[3],
        }
        for row in rows
    ]
    total_count = int(rows[0][4]) if rows else 0
    return JsonResponse(
        {
            "ok": True,
            "functions": functions,
            "page": page,
            "page_size": page_size,
            "total_count": total_count,
        }
    )


@require_http_methods(["POST"])
def distribution_tables(request):
    """Возвращает таблицы, доступные для анализа распределения."""
    payload = _read_json_body(request)
    db_connection, error_response = _require_greenplum_connection(request, payload)
    if error_response:
        return error_response
    tables_query = f"""
        SELECT
            namespace.nspname AS schema_name,
            table_class.relname AS table_name,
            CASE table_class.relkind
                WHEN 'm' THEN 'Материализованное представление'
                WHEN 'p' THEN 'Партиционированная таблица'
                ELSE 'Таблица'
            END AS object_type
        FROM pg_catalog.pg_class AS table_class
        JOIN pg_catalog.pg_namespace AS namespace
            ON namespace.oid = table_class.relnamespace
        WHERE table_class.relkind IN ('r', 'p', 'm')
          AND namespace.nspname NOT IN {EXCLUDED_SYSTEM_SCHEMAS_SQL}
          AND namespace.nspname NOT LIKE 'pg_toast%%'
        ORDER BY namespace.nspname ASC, table_class.relname ASC;
    """

    try:
        rows = _fetch_db_rows(db_connection, tables_query)
        tables = [
            {"schema_name": row[0], "table_name": row[1], "object_type": row[2]}
            for row in rows
        ]
    except Exception as exc:
        return JsonResponse(
            {
                "ok": False,
                "message": _safe_db_error_message("Не удалось получить список таблиц", exc),
            },
            status=400,
        )

    return JsonResponse({"ok": True, "tables": tables})


@require_http_methods(["POST"])
def distribution_info(request):
    """Возвращает распределение строк таблицы по сегментам."""
    payload = _read_json_body(request)
    connection_id = payload.get("id")
    schema_name = (payload.get("schema_name") or "").strip()
    table_name = (payload.get("table_name") or "").strip()
    if not connection_id:
        return JsonResponse(
            {"ok": False, "message": "Подключение не выбрано"}, status=400
        )
    if not schema_name or not table_name:
        return JsonResponse({"ok": False, "message": "Таблица не выбрана"}, status=400)

    db_connection = _get_connection_for_request(request, connection_id)
    if db_connection.db_type != "Greenplum":
        return _greenplum_only_error()
    validate_query = """
        SELECT 1
        FROM pg_catalog.pg_class AS table_class
        JOIN pg_catalog.pg_namespace AS namespace
            ON namespace.oid = table_class.relnamespace
        WHERE namespace.nspname = %s
          AND table_class.relname = %s
          AND table_class.relkind IN ('r', 'p', 'm')
        LIMIT 1;
    """
    distribution_query = sql.SQL("""
        SELECT gp_segment_id::int AS segment_id, COUNT(*)::bigint AS row_count
        FROM {}.{}
        GROUP BY gp_segment_id
        ORDER BY gp_segment_id ASC;
    """).format(sql.Identifier(schema_name), sql.Identifier(table_name))

    try:
        with _open_database_connection(db_connection) as connection:
            with connection.cursor() as cursor:
                cursor.execute(validate_query, [schema_name, table_name])
                if not cursor.fetchone():
                    return JsonResponse(
                        {"ok": False, "message": "Выбранная таблица не найдена"},
                        status=404,
                    )
                cursor.execute(distribution_query)
                rows = cursor.fetchall()
    except Exception as exc:
        return JsonResponse(
            {
                "ok": False,
                "message": _safe_db_error_message("Не удалось получить распределение", exc),
            },
            status=400,
        )

    segments = [{"segment_id": int(row[0]), "row_count": int(row[1])} for row in rows]
    counts = [item["row_count"] for item in segments]
    total_rows = sum(counts)
    used_segments = sum(1 for count in counts if count > 0)
    min_rows = min(counts) if counts else 0
    max_rows = max(counts) if counts else 0
    avg_rows = round(total_rows / len(counts), 2) if counts else 0
    skew_ratio = (
        round(max_rows / min_rows, 2)
        if min_rows
        else (float(max_rows) if max_rows else 0)
    )
    status = (
        "высокий" if skew_ratio >= 1.5 else "средний" if skew_ratio >= 1.2 else "норм."
    )

    return JsonResponse(
        {
            "ok": True,
            "schema_name": schema_name,
            "table_name": table_name,
            "segments": segments,
            "metrics": {
                "total_rows": total_rows,
                "used_segments": used_segments,
                "min_rows": min_rows,
                "max_rows": max_rows,
                "avg_rows": avg_rows,
                "skew_ratio": skew_ratio,
                "status": status,
            },
        }
    )


@require_http_methods(["POST"])
def database_temp_table_sizes(request):
    """Возвращает размеры активных временных таблиц."""
    payload = _read_json_body(request)
    db_connection, error_response = _require_payload_connection(request, payload)
    if error_response:
        return error_response
    page, page_size, offset, search, sort_column, direction = _list_query_params(
        payload,
        {
            "schema_name": "schema_name",
            "table_name": "table_name",
            "table_owner": "table_owner",
            "size_bytes": "size_bytes",
            "session_label": "session_label",
        },
        "size_bytes",
    )

    where_sql = ""
    params = []
    if search:
        where_sql, params = _multi_column_search_filter(
            search,
            (
                "namespace.nspname",
                "table_class.relname",
                "owner.rolname",
                "(namespace.nspname || '.' || table_class.relname)",
            ),
        )

    temp_table_sizes_query = f"""
        WITH temp_table_sizes AS (
            SELECT
                namespace.nspname AS schema_name,
                table_class.relname AS table_name,
                COALESCE(owner.rolname, '-') AS table_owner,
                pg_total_relation_size(table_class.oid)::bigint AS size_bytes,
                CASE
                    WHEN namespace.nspname ~ '^pg_temp_[0-9]+$'
                    THEN 'backend ' || substring(namespace.nspname FROM '^pg_temp_([0-9]+)$')
                    ELSE '-'
                END AS session_label
            FROM pg_catalog.pg_class AS table_class
            JOIN pg_catalog.pg_namespace AS namespace
                ON namespace.oid = table_class.relnamespace
            LEFT JOIN pg_catalog.pg_roles AS owner
                ON owner.oid = table_class.relowner
            WHERE table_class.relkind IN ('r', 'p')
              AND (table_class.relpersistence = 't' OR namespace.nspname LIKE 'pg_temp_%%')
              AND namespace.nspname NOT LIKE 'pg_toast%%'
              {where_sql}
        )
        SELECT
            schema_name,
            table_name,
            table_owner,
            size_bytes,
            pg_size_pretty(size_bytes) AS table_size,
            session_label,
            COUNT(*) OVER() AS total_count
        FROM temp_table_sizes
        ORDER BY {sort_column} {direction}, schema_name ASC, table_name ASC
        LIMIT %s OFFSET %s;
    """

    temp_table_distribution_query = f"""
        WITH temp_table_sizes AS (
            SELECT
                namespace.nspname AS schema_name,
                table_class.relname AS table_name,
                pg_total_relation_size(table_class.oid)::bigint AS size_bytes
            FROM pg_catalog.pg_class AS table_class
            JOIN pg_catalog.pg_namespace AS namespace
                ON namespace.oid = table_class.relnamespace
            LEFT JOIN pg_catalog.pg_roles AS owner
                ON owner.oid = table_class.relowner
            WHERE table_class.relkind IN ('r', 'p')
              AND (table_class.relpersistence = 't' OR namespace.nspname LIKE 'pg_temp_%%')
              AND namespace.nspname NOT LIKE 'pg_toast%%'
              {where_sql}
        )
        SELECT
            schema_name,
            table_name,
            size_bytes,
            pg_size_pretty(size_bytes) AS table_size
        FROM temp_table_sizes
        ORDER BY size_bytes DESC, schema_name ASC, table_name ASC;
    """

    try:
        rows, distribution_rows = _fetch_db_resultsets(
            db_connection,
            (temp_table_sizes_query, [*params, page_size, offset]),
            (temp_table_distribution_query, params),
        )
    except Exception as exc:
        return JsonResponse(
            {
                "ok": False,
                "message": _safe_db_error_message(
                    "Не удалось получить временные таблицы", exc
                ),
            },
            status=400,
        )

    temp_tables = [
        {
            "schema_name": row[0],
            "table_name": row[1],
            "table_owner": row[2],
            "size_bytes": int(row[3]),
            "table_size": row[4],
            "session_label": row[5],
        }
        for row in rows
    ]
    temp_table_distribution = [
        {
            "schema_name": row[0],
            "table_name": row[1],
            "size_bytes": int(row[2] or 0),
            "table_size": row[3],
        }
        for row in distribution_rows
    ]
    total_count = int(rows[0][6]) if rows else len(temp_table_distribution)
    return JsonResponse(
        {
            "ok": True,
            "temp_tables": temp_tables,
            "temp_table_distribution": temp_table_distribution,
            "page": page,
            "page_size": page_size,
            "total_count": total_count,
        }
    )
