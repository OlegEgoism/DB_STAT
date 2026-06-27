import json

import psycopg2
from psycopg2 import sql
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_http_methods

from db_statistics.models import DBConnection

CONNECTION_TIMEOUT_SECONDS = 5


@ensure_csrf_cookie
def home(request):
    """Главная страница мониторинга БД."""
    return render(request, "home.html")


def cluster_status(request):
    """HTMX-фрагмент с текущим статусом кластера.

    Пока данные моковые; дальше сюда можно подключить результаты SQL-проверок
    PostgreSQL/Greenplum из раздела мониторинга работоспособности.
    """
    return render(
        request,
        "partials/_cluster_status.html",
        {"cluster_status_color": "green", "cluster_status_text": "Кластер работает"},
    )


def _connection_to_dict(connection):
    return {
        "id": str(connection.pk),
        "name": connection.name,
        "host": connection.host,
        "port": connection.port,
        "database": connection.database,
        "user": connection.username,
        "db_type": connection.db_type,
        "status": "offline",
    }


def _read_json_body(request):
    try:
        return json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return {}


def _escape_like_pattern(value):
    return value.replace('!', '!!').replace('%', '!%').replace('_', '!_')


def _connection_kwargs(host, port, database, username, password, ssl=True):
    return {
        "host": host,
        "port": port,
        "dbname": database,
        "user": username,
        "password": password,
        "connect_timeout": CONNECTION_TIMEOUT_SECONDS,
        "sslmode": "prefer" if ssl else "disable",
    }


def _test_connection_params(host, port, database, username, password, ssl):
    with psycopg2.connect(**_connection_kwargs(host, port, database, username, password, ssl)) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()


@require_http_methods(["GET", "POST"])
def connections(request):
    if request.method == "GET":
        items = DBConnection.objects.filter(is_active=True).order_by("name", "host")
        return JsonResponse({"connections": [_connection_to_dict(item) for item in items]})

    payload = _read_json_body(request)
    required_fields = ["name", "host", "port", "database", "user"]
    if any(not payload.get(field) for field in required_fields):
        return JsonResponse({"ok": False, "message": "Заполните все обязательные поля"}, status=400)

    defaults = {
        "username": payload["user"].strip(),
        "db_type": payload.get("db_type") or "PostgreSQL",
        "is_active": True,
    }
    if payload.get("password"):
        defaults["password"] = payload["password"]

    if payload.get("id"):
        connection = get_object_or_404(DBConnection, pk=payload["id"], is_active=True)
        connection.name = payload["name"].strip()
        connection.host = payload["host"].strip()
        connection.port = int(payload["port"])
        connection.database = payload["database"].strip()
        for field, value in defaults.items():
            setattr(connection, field, value)
        connection.save()
        return JsonResponse({"ok": True, "created": False, "connection": _connection_to_dict(connection)})

    connection, created = DBConnection.objects.update_or_create(
        name=payload["name"].strip(),
        host=payload["host"].strip(),
        port=int(payload["port"]),
        database=payload["database"].strip(),
        defaults={**defaults, "password": payload.get("password", "")},
    )
    return JsonResponse({"ok": True, "created": created, "connection": _connection_to_dict(connection)}, status=201 if created else 200)


@require_http_methods(["POST"])
def test_connection(request):
    payload = _read_json_body(request)
    connection_id = payload.get("id")

    if connection_id:
        connection = get_object_or_404(DBConnection, pk=connection_id, is_active=True)
        if all(payload.get(field) for field in ["name", "host", "port", "database", "user"]):
            params = {
                "host": payload["host"].strip(),
                "port": int(payload["port"]),
                "database": payload["database"].strip(),
                "username": payload["user"].strip(),
                "password": payload.get("password") or connection.password,
                "ssl": payload.get("ssl", True),
            }
            name = payload["name"].strip()
        else:
            params = {
                "host": connection.host,
                "port": connection.port,
                "database": connection.database,
                "username": connection.username,
                "password": connection.password,
                "ssl": payload.get("ssl", True),
            }
            name = connection.name
    else:
        required_fields = ["name", "host", "port", "database", "user"]
        if any(not payload.get(field) for field in required_fields):
            return JsonResponse({"ok": False, "message": "Заполните все обязательные поля"}, status=400)
        params = {
            "host": payload["host"].strip(),
            "port": int(payload["port"]),
            "database": payload["database"].strip(),
            "username": payload["user"].strip(),
            "password": payload.get("password", ""),
            "ssl": payload.get("ssl", True),
        }
        name = payload["name"].strip()

    try:
        _test_connection_params(**params)
    except Exception as exc:
        return JsonResponse({"ok": False, "message": f"Не удалось подключиться к {name}: {exc}"}, status=400)

    return JsonResponse({"ok": True, "message": f"Подключение к {name} успешно"})

@require_http_methods(["POST"])
def delete_connection(request):
    payload = _read_json_body(request)
    connection_id = payload.get("id")
    if not connection_id:
        return JsonResponse({"ok": False, "message": "Подключение не выбрано"}, status=400)

    connection = get_object_or_404(DBConnection, pk=connection_id, is_active=True)
    connection.is_active = False
    connection.save(update_fields=["is_active", "updated"])
    return JsonResponse({"ok": True, "message": f"Подключение {connection.name} удалено"})


@require_http_methods(["POST"])
def database_overview(request):
    payload = _read_json_body(request)
    connection_id = payload.get("id")
    if not connection_id:
        return JsonResponse({"ok": False, "message": "Подключение не выбрано"}, status=400)

    db_connection = get_object_or_404(DBConnection, pk=connection_id, is_active=True)
    overview_query = """
        WITH relation_sizes AS (
            SELECT
                table_class.oid,
                table_class.relkind,
                table_class.relpersistence,
                namespace.nspname,
                pg_total_relation_size(table_class.oid)::bigint AS total_size_bytes,
                CASE
                    WHEN table_class.relkind IN ('r', 'p', 'm')
                    THEN pg_indexes_size(table_class.oid)::bigint
                    ELSE 0::bigint
                END AS index_size_bytes
            FROM pg_catalog.pg_class AS table_class
            JOIN pg_catalog.pg_namespace AS namespace
                ON namespace.oid = table_class.relnamespace
            WHERE table_class.relkind IN ('r', 'p', 'm')
              AND namespace.nspname NOT IN ('pg_catalog', 'information_schema', 'gp_toolkit')
              AND namespace.nspname NOT LIKE 'pg_toast%%'
        )
        SELECT
            version() AS database_version,
            current_setting('statement_mem', true) AS statement_mem,
            current_setting('max_statement_mem', true) AS max_statement_mem,
            current_setting('gp_vmem_protect_limit', true) AS gp_vmem_protect_limit,
            pg_database_size(%s)::bigint AS total_size_bytes,
            COALESCE(SUM(index_size_bytes), 0)::bigint AS index_size_bytes,
            GREATEST(pg_database_size(%s)::bigint - COALESCE(SUM(index_size_bytes), 0)::bigint, 0)::bigint AS data_size_without_indexes_bytes,
            COALESCE(SUM(total_size_bytes) FILTER (WHERE relpersistence = 't' OR nspname LIKE 'pg_temp_%%'), 0)::bigint AS temp_table_size_bytes,
            COALESCE(SUM(total_size_bytes) FILTER (WHERE relkind = 'm'), 0)::bigint AS materialized_view_size_bytes,
            (SELECT COUNT(*) FROM pg_catalog.pg_roles WHERE rolcanlogin)::bigint AS user_count,
            (SELECT COUNT(*) FROM pg_catalog.pg_roles WHERE NOT rolcanlogin)::bigint AS group_count
        FROM relation_sizes;
    """

    try:
        with psycopg2.connect(
            **_connection_kwargs(
                db_connection.host,
                db_connection.port,
                db_connection.database,
                db_connection.username,
                db_connection.password,
            )
        ) as connection:
            with connection.cursor() as cursor:
                cursor.execute(overview_query, [db_connection.database, db_connection.database])
                row = cursor.fetchone()
    except Exception as exc:
        return JsonResponse({"ok": False, "message": f"Не удалось получить обзор БД: {exc}"}, status=400)

    metrics = [
        {"key": "total", "label": "Общий размер БД", "size_bytes": int(row[4] or 0)},
        {"key": "indexes", "label": "Размер индексов", "size_bytes": int(row[5] or 0)},
        {"key": "data_without_indexes", "label": "Размер БД без индексов", "size_bytes": int(row[6] or 0)},
        {"key": "temp_tables", "label": "Размер временных таблиц", "size_bytes": int(row[7] or 0)},
        {"key": "materialized_views", "label": "Размер материализованных представлений", "size_bytes": int(row[8] or 0)},
    ]
    memory_settings = [
        {"key": "statement_mem", "label": "Память на один запрос", "setting": "statement_mem", "value": row[1] or "—"},
        {"key": "max_statement_mem", "label": "Максимальная память на запрос", "setting": "max_statement_mem", "value": row[2] or "—"},
        {"key": "gp_vmem_protect_limit", "label": "Лимит виртуальной памяти сегмента", "setting": "gp_vmem_protect_limit", "value": row[3] or "—"},
    ]
    connection_info = [
        {"label": "Хост", "value": db_connection.host},
        {"label": "Порт", "value": db_connection.port},
    ]
    role_counts = [
        {"label": "Пользователи", "count": int(row[9] or 0)},
        {"label": "Группы", "count": int(row[10] or 0)},
    ]
    return JsonResponse({"ok": True, "database": db_connection.database, "database_version": row[0] or "—", "connection_info": connection_info, "metrics": metrics, "memory_settings": memory_settings, "role_counts": role_counts})


@require_http_methods(["POST"])
def database_size(request):
    payload = _read_json_body(request)
    connection_id = payload.get("id")
    if not connection_id:
        return JsonResponse({"ok": False, "message": "Подключение не выбрано"}, status=400)

    db_connection = get_object_or_404(DBConnection, pk=connection_id, is_active=True)
    size_query = """
        SELECT
            pg_database_size(%s) AS size_bytes,
            pg_size_pretty(pg_database_size(%s)) AS size_pretty;
    """

    try:
        with psycopg2.connect(
            **_connection_kwargs(
                db_connection.host,
                db_connection.port,
                db_connection.database,
                db_connection.username,
                db_connection.password,
            )
        ) as connection:
            with connection.cursor() as cursor:
                cursor.execute(size_query, [db_connection.database, db_connection.database])
                size_bytes, size_pretty = cursor.fetchone()
    except Exception as exc:
        return JsonResponse({"ok": False, "message": f"Не удалось получить размер БД: {exc}"}, status=400)

    return JsonResponse(
        {
            "ok": True,
            "database": db_connection.database,
            "size_bytes": int(size_bytes),
            "size_pretty": size_pretty,
        }
    )


@require_http_methods(["POST"])
def active_queries(request):
    payload = _read_json_body(request)
    connection_id = payload.get("id")
    if not connection_id:
        return JsonResponse({"ok": False, "message": "Подключение не выбрано"}, status=400)

    db_connection = get_object_or_404(DBConnection, pk=connection_id, is_active=True)
    active_queries_query = """
        SELECT DISTINCT
            activity.pid,
            activity.usename,
            namespace.nspname || '.' || relation.relname AS relation_name,
            activity.state,
            now() - activity.query_start AS duration,
            activity.query
        FROM pg_catalog.pg_stat_activity AS activity
        JOIN pg_catalog.pg_locks AS locks
            ON locks.pid = activity.pid
           AND locks.relation IS NOT NULL
        JOIN pg_catalog.pg_class AS relation
            ON relation.oid = locks.relation
        JOIN pg_catalog.pg_namespace AS namespace
            ON namespace.oid = relation.relnamespace
        WHERE activity.state = 'active'
        ORDER BY duration DESC;
    """

    try:
        with psycopg2.connect(
            **_connection_kwargs(
                db_connection.host,
                db_connection.port,
                db_connection.database,
                db_connection.username,
                db_connection.password,
            )
        ) as connection:
            with connection.cursor() as cursor:
                cursor.execute(active_queries_query)
                rows = cursor.fetchall()
    except Exception as exc:
        return JsonResponse({"ok": False, "message": f"Не удалось получить активные запросы: {exc}"}, status=400)

    queries = []
    for row in rows:
        duration = row[4]
        queries.append(
            {
                "pid": row[0],
                "username": row[1] or "—",
                "relation_name": row[2] or "—",
                "state": row[3] or "—",
                "duration": str(duration).split(".")[0] if duration else "—",
                "sql": row[5] or "—",
            }
        )
    return JsonResponse({"ok": True, "queries": queries, "total_count": len(queries)})


@require_http_methods(["POST"])
def database_schema_sizes(request):
    payload = _read_json_body(request)
    connection_id = payload.get("id")
    if not connection_id:
        return JsonResponse({"ok": False, "message": "Подключение не выбрано"}, status=400)

    db_connection = get_object_or_404(DBConnection, pk=connection_id, is_active=True)
    page_size = 100
    page = max(int(payload.get("page") or 1), 1)
    offset = (page - 1) * page_size
    search = (payload.get("search") or "").strip()
    sort = payload.get("sort") or "size_bytes"
    direction = "ASC" if payload.get("direction") == "asc" else "DESC"
    sort_columns = {
        "schema_name": "schema_name",
        "schema_owner": "schema_owner",
        "table_count": "table_count",
        "size_bytes": "size_bytes",
    }
    sort_column = sort_columns.get(sort, "size_bytes")

    where_sql = ""
    params = []
    if search:
        where_sql = "AND (namespace.nspname ILIKE %s OR owner.rolname ILIKE %s)"
        params.extend([f"%{search}%", f"%{search}%"])

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
              AND namespace.nspname NOT IN ('pg_catalog', 'information_schema', 'gp_toolkit')
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

    try:
        with psycopg2.connect(
            **_connection_kwargs(
                db_connection.host,
                db_connection.port,
                db_connection.database,
                db_connection.username,
                db_connection.password,
            )
        ) as connection:
            with connection.cursor() as cursor:
                cursor.execute(schema_sizes_query, [*params, page_size, offset])
                rows = cursor.fetchall()
    except Exception as exc:
        return JsonResponse({"ok": False, "message": f"Не удалось получить размеры схем: {exc}"}, status=400)

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
    total_count = int(rows[0][5]) if rows else 0
    return JsonResponse({"ok": True, "schemas": schemas, "page": page, "page_size": page_size, "total_count": total_count})


@require_http_methods(["POST"])
def database_table_sizes(request):
    payload = _read_json_body(request)
    connection_id = payload.get("id")
    if not connection_id:
        return JsonResponse({"ok": False, "message": "Подключение не выбрано"}, status=400)

    db_connection = get_object_or_404(DBConnection, pk=connection_id, is_active=True)
    page_size = 100
    page = max(int(payload.get("page") or 1), 1)
    offset = (page - 1) * page_size
    search = (payload.get("search") or "").strip()
    sort = payload.get("sort") or "size_bytes"
    direction = "ASC" if payload.get("direction") == "asc" else "DESC"
    sort_columns = {
        "schema_name": "schema_name",
        "table_name": "table_name",
        "table_owner": "table_owner",
        "size_bytes": "size_bytes",
        "index_size_bytes": "index_size_bytes",
        "index_count": "index_count",
        "row_count": "row_count",
    }
    sort_column = sort_columns.get(sort, "size_bytes")

    where_sql = ""
    params = []
    if search:
        search_pattern = f"%{_escape_like_pattern(search)}%"
        where_sql = """
          AND (
              namespace.nspname ILIKE %s ESCAPE '!'
              OR table_class.relname ILIKE %s ESCAPE '!'
              OR (namespace.nspname || '.' || table_class.relname) ILIKE %s ESCAPE '!'
          )
        """
        params.extend([search_pattern, search_pattern, search_pattern])

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
              AND namespace.nspname NOT IN ('pg_catalog', 'information_schema', 'gp_toolkit')
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

    try:
        with psycopg2.connect(
            **_connection_kwargs(
                db_connection.host,
                db_connection.port,
                db_connection.database,
                db_connection.username,
                db_connection.password,
            )
        ) as connection:
            with connection.cursor() as cursor:
                cursor.execute(table_sizes_query, [*params, page_size, offset])
                rows = cursor.fetchall()
    except Exception as exc:
        return JsonResponse({"ok": False, "message": f"Не удалось получить размеры таблиц: {exc}"}, status=400)

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
    total_count = int(rows[0][9]) if rows else 0
    return JsonResponse({"ok": True, "tables": tables, "page": page, "page_size": page_size, "total_count": total_count})



@require_http_methods(["POST"])
def database_views_list(request):
    payload = _read_json_body(request)
    connection_id = payload.get("id")
    if not connection_id:
        return JsonResponse({"ok": False, "message": "Подключение не выбрано"}, status=400)

    db_connection = get_object_or_404(DBConnection, pk=connection_id, is_active=True)
    page_size = 100
    page = max(int(payload.get("page") or 1), 1)
    offset = (page - 1) * page_size
    search = (payload.get("search") or "").strip()
    sort = payload.get("sort") or "schema_name"
    direction = "ASC" if payload.get("direction") == "asc" else "DESC"
    sort_columns = {
        "schema_name": "schema_name",
        "view_name": "view_name",
        "view_owner": "view_owner",
        "view_type": "view_type",
        "size_bytes": "size_bytes",
        "index_size_bytes": "index_size_bytes",
        "row_count": "row_count",
    }
    sort_column = sort_columns.get(sort, "schema_name")

    where_sql = ""
    params = []
    if search:
        search_pattern = f"%{_escape_like_pattern(search)}%"
        where_sql = """
          AND (
              namespace.nspname ILIKE %s ESCAPE '!'
              OR view_class.relname ILIKE %s ESCAPE '!'
              OR owner.rolname ILIKE %s ESCAPE '!'
              OR (namespace.nspname || '.' || view_class.relname) ILIKE %s ESCAPE '!'
          )
        """
        params.extend([search_pattern, search_pattern, search_pattern, search_pattern])

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
              AND namespace.nspname NOT IN ('pg_catalog', 'information_schema', 'gp_toolkit')
              AND namespace.nspname NOT LIKE 'pg_toast%%'
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
            COUNT(*) OVER() AS total_count
        FROM database_views
        ORDER BY {sort_column} {direction}, schema_name ASC, view_name ASC
        LIMIT %s OFFSET %s;
    """

    try:
        with psycopg2.connect(
            **_connection_kwargs(
                db_connection.host,
                db_connection.port,
                db_connection.database,
                db_connection.username,
                db_connection.password,
            )
        ) as connection:
            with connection.cursor() as cursor:
                cursor.execute(views_query, [*params, page_size, offset])
                rows = cursor.fetchall()
    except Exception as exc:
        return JsonResponse({"ok": False, "message": f"Не удалось получить представления: {exc}"}, status=400)

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
    return JsonResponse({"ok": True, "views": items, "page": page, "page_size": page_size, "total_count": total_count})


@require_http_methods(["POST"])
def distribution_tables(request):
    payload = _read_json_body(request)
    connection_id = payload.get("id")
    if not connection_id:
        return JsonResponse({"ok": False, "message": "Подключение не выбрано"}, status=400)

    db_connection = get_object_or_404(DBConnection, pk=connection_id, is_active=True)
    tables_query = """
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
          AND namespace.nspname NOT IN ('pg_catalog', 'information_schema', 'gp_toolkit')
          AND namespace.nspname NOT LIKE 'pg_toast%%'
        ORDER BY namespace.nspname ASC, table_class.relname ASC;
    """

    try:
        with psycopg2.connect(
            **_connection_kwargs(
                db_connection.host,
                db_connection.port,
                db_connection.database,
                db_connection.username,
                db_connection.password,
            )
        ) as connection:
            with connection.cursor() as cursor:
                cursor.execute(tables_query)
                tables = [{"schema_name": row[0], "table_name": row[1], "object_type": row[2]} for row in cursor.fetchall()]
    except Exception as exc:
        return JsonResponse({"ok": False, "message": f"Не удалось получить список таблиц: {exc}"}, status=400)

    return JsonResponse({"ok": True, "tables": tables})


@require_http_methods(["POST"])
def distribution_info(request):
    payload = _read_json_body(request)
    connection_id = payload.get("id")
    schema_name = (payload.get("schema_name") or "").strip()
    table_name = (payload.get("table_name") or "").strip()
    if not connection_id:
        return JsonResponse({"ok": False, "message": "Подключение не выбрано"}, status=400)
    if not schema_name or not table_name:
        return JsonResponse({"ok": False, "message": "Таблица не выбрана"}, status=400)

    db_connection = get_object_or_404(DBConnection, pk=connection_id, is_active=True)
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
        with psycopg2.connect(
            **_connection_kwargs(
                db_connection.host,
                db_connection.port,
                db_connection.database,
                db_connection.username,
                db_connection.password,
            )
        ) as connection:
            with connection.cursor() as cursor:
                cursor.execute(validate_query, [schema_name, table_name])
                if not cursor.fetchone():
                    return JsonResponse({"ok": False, "message": "Выбранная таблица не найдена"}, status=404)
                cursor.execute(distribution_query)
                rows = cursor.fetchall()
    except Exception as exc:
        return JsonResponse({"ok": False, "message": f"Не удалось получить распределение: {exc}"}, status=400)

    segments = [{"segment_id": int(row[0]), "row_count": int(row[1])} for row in rows]
    counts = [item["row_count"] for item in segments]
    total_rows = sum(counts)
    min_rows = min(counts) if counts else 0
    max_rows = max(counts) if counts else 0
    avg_rows = round(total_rows / len(counts), 2) if counts else 0
    skew_ratio = round(max_rows / min_rows, 2) if min_rows else (float(max_rows) if max_rows else 0)
    status = "высокий" if skew_ratio >= 1.5 else "средний" if skew_ratio >= 1.2 else "норм."

    return JsonResponse(
        {
            "ok": True,
            "schema_name": schema_name,
            "table_name": table_name,
            "segments": segments,
            "metrics": {
                "total_rows": total_rows,
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
    payload = _read_json_body(request)
    connection_id = payload.get("id")
    if not connection_id:
        return JsonResponse({"ok": False, "message": "Подключение не выбрано"}, status=400)

    db_connection = get_object_or_404(DBConnection, pk=connection_id, is_active=True)
    page_size = 100
    page = max(int(payload.get("page") or 1), 1)
    offset = (page - 1) * page_size
    search = (payload.get("search") or "").strip()
    sort = payload.get("sort") or "size_bytes"
    direction = "ASC" if payload.get("direction") == "asc" else "DESC"
    sort_columns = {
        "schema_name": "schema_name",
        "table_name": "table_name",
        "table_owner": "table_owner",
        "size_bytes": "size_bytes",
        "session_label": "session_label",
    }
    sort_column = sort_columns.get(sort, "size_bytes")

    where_sql = ""
    params = []
    if search:
        search_pattern = f"%{_escape_like_pattern(search)}%"
        where_sql = """
          AND (
              namespace.nspname ILIKE %s ESCAPE '!'
              OR table_class.relname ILIKE %s ESCAPE '!'
              OR owner.rolname ILIKE %s ESCAPE '!'
              OR (namespace.nspname || '.' || table_class.relname) ILIKE %s ESCAPE '!'
          )
        """
        params.extend([search_pattern, search_pattern, search_pattern, search_pattern])

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

    try:
        with psycopg2.connect(
            **_connection_kwargs(
                db_connection.host,
                db_connection.port,
                db_connection.database,
                db_connection.username,
                db_connection.password,
            )
        ) as connection:
            with connection.cursor() as cursor:
                cursor.execute(temp_table_sizes_query, [*params, page_size, offset])
                rows = cursor.fetchall()
    except Exception as exc:
        return JsonResponse({"ok": False, "message": f"Не удалось получить временные таблицы: {exc}"}, status=400)

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
    total_count = int(rows[0][6]) if rows else 0
    return JsonResponse({"ok": True, "temp_tables": temp_tables, "page": page, "page_size": page_size, "total_count": total_count})

@require_http_methods(["POST"])
def segments_info(request):
    payload = _read_json_body(request)
    connection_id = payload.get("id")
    if not connection_id:
        return JsonResponse({"ok": False, "message": "Подключение не выбрано"}, status=400)

    db_connection = get_object_or_404(DBConnection, pk=connection_id, is_active=True)
    config_query = """
        SELECT
            content AS segment,
            role,
            preferred_role,
            mode,
            status,
            port,
            hostname,
            address
        FROM pg_catalog.gp_segment_configuration
        ORDER BY dbid ASC;
    """
    health_query = """
        SELECT
            'Здоровье кластера' as check_name,
            CASE
                WHEN COUNT(*) = SUM(CASE WHEN status = 'u' THEN 1 ELSE 0 END)
                     AND COUNT(*) = SUM(CASE WHEN mode = 's' THEN 1 ELSE 0 END)
                THEN 'Все сегменты подняты и синхронизированы'
                WHEN COUNT(*) > SUM(CASE WHEN status = 'u' THEN 1 ELSE 0 END)
                THEN 'Есть проблемы: ' ||
                     (COUNT(*) - SUM(CASE WHEN status = 'u' THEN 1 ELSE 0 END)) ||
                     ' сегментов не подняты'
                ELSE 'Критические проблемы'
            END as status
        FROM gp_segment_configuration
        WHERE content != -1;
    """
    metrics_query = """
        SELECT 'Общее количество сегментов', COUNT(*)::numeric
        FROM gp_segment_configuration
        WHERE content >= 0
        UNION ALL
        SELECT 'Cегменты работают', COUNT(*) FILTER (WHERE status = 'u')::numeric
        FROM gp_segment_configuration
        WHERE content >= 0
        UNION ALL
        SELECT 'Cегменты не работают', COUNT(*) FILTER (WHERE status = 'd')::numeric
        FROM gp_segment_configuration
        WHERE content >= 0
        UNION ALL
        SELECT 'Cинхронизированные сегменты', COUNT(*) FILTER (WHERE mode = 's')::numeric
        FROM gp_segment_configuration
        WHERE content >= 0
        UNION ALL
        SELECT 'Основные сегменты', COUNT(*) FILTER (WHERE role = 'p')::numeric
        FROM gp_segment_configuration
        WHERE content >= 0
        UNION ALL
        SELECT 'Зеркальные сегменты', COUNT(*) FILTER (WHERE role = 'm')::numeric
        FROM gp_segment_configuration
        WHERE content >= 0
        UNION ALL
        SELECT 'Процент здоровья', ROUND(100.0 * COUNT(*) FILTER (WHERE status = 'u') / COUNT(*))::numeric
        FROM gp_segment_configuration
        WHERE content >= 0;
    """
    try:
        with psycopg2.connect(
            **_connection_kwargs(
                db_connection.host,
                db_connection.port,
                db_connection.database,
                db_connection.username,
                db_connection.password,
            )
        ) as connection:
            with connection.cursor() as cursor:
                cursor.execute(config_query)
                segments = [
                    {
                        "segment": row[0],
                        "role": row[1],
                        "preferred_role": row[2],
                        "mode": row[3],
                        "status": row[4],
                        "port": row[5],
                        "hostname": row[6],
                        "address": row[7],
                    }
                    for row in cursor.fetchall()
                ]
                cursor.execute(health_query)
                health_row = cursor.fetchone()
                cursor.execute(metrics_query)
                metrics = [{"name": row[0], "value": float(row[1])} for row in cursor.fetchall()]
    except Exception as exc:
        return JsonResponse({"ok": False, "message": f"Не удалось получить информацию о сегментах: {exc}"}, status=400)

    return JsonResponse({"ok": True, "segments": segments, "health": health_row[1] if health_row else "Нет данных", "metrics": metrics})
