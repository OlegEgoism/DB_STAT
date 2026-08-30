from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

from db_statistics.models import MaintenanceJob
from db_statistics.view_helpers import (
    EXCLUDED_SYSTEM_SCHEMAS_SQL,
    _current_db_user,
    _database_roles_list,
    _destructive_action_permission_error,
    _escape_like_pattern,
    _fetch_db_row,
    _fetch_db_rows,
    _format_bytes,
    _list_query_params,
    _maintenance_operation_audit_info,
    _parse_pg_size_to_bytes,
    _query_or_error,
    _read_json_body,
    _require_payload_connection,
    _serialize_maintenance_job,
    _submit_maintenance_job,
    _write_audit,
)


@require_http_methods(["POST"])
def memory_overview(request):
    """Возвращает параметры и показатели использования памяти базы данных."""
    payload = _read_json_body(request)
    db_connection, error_response = _require_payload_connection(request, payload)
    if error_response:
        return error_response
    memory_query = f"""
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
              AND namespace.nspname NOT IN {EXCLUDED_SYSTEM_SCHEMAS_SQL}
              AND namespace.nspname NOT LIKE 'pg_toast%%'
        )
        SELECT
            current_setting('gp_vmem_protect_limit', true) AS gp_vmem_protect_limit,
            current_setting('shared_buffers', true) AS shared_buffers,
            current_setting('work_mem', true) AS work_mem,
            current_setting('maintenance_work_mem', true) AS maintenance_work_mem,
            current_setting('statement_mem', true) AS statement_mem,
            current_setting('max_statement_mem', true) AS max_statement_mem,
            pg_database_size(%s)::bigint AS total_size_bytes,
            COALESCE(SUM(index_size_bytes), 0)::bigint AS index_size_bytes,
            GREATEST(pg_database_size(%s)::bigint - COALESCE(SUM(index_size_bytes), 0)::bigint, 0)::bigint AS data_size_without_indexes_bytes,
            COALESCE(SUM(total_size_bytes) FILTER (WHERE relpersistence = 't' OR nspname LIKE 'pg_temp_%%'), 0)::bigint AS temp_table_size_bytes,
            COALESCE(SUM(total_size_bytes) FILTER (WHERE relkind = 'm'), 0)::bigint AS materialized_view_size_bytes
        FROM relation_sizes;
    """

    row, error_response = _query_or_error(
        "Не удалось получить параметры памяти",
        lambda: _fetch_db_row(
            db_connection, memory_query, [db_connection.database, db_connection.database]
        ),
    )
    if error_response:
        return error_response

    settings = [
        {
            "key": "gp_vmem_protect_limit",
            "label": "Лимит виртуальной памяти сегмента",
            "value": row[0] or "—",
            "role": "Защита OOM",
        },
        {
            "key": "shared_buffers",
            "label": "Кэш данных",
            "value": row[1] or "—",
            "role": "Буферы",
        },
        {
            "key": "work_mem",
            "label": "Память операций",
            "value": row[2] or "—",
            "role": "Сортировка/Hash",
        },
        {
            "key": "maintenance_work_mem",
            "label": "Память обслуживания",
            "value": row[3] or "—",
            "role": "Очистка / создание индекса",
        },
        {
            "key": "statement_mem",
            "label": "Память запроса",
            "value": row[4] or "—",
            "role": "Лимит запроса",
        },
        {
            "key": "max_statement_mem",
            "label": "Максимальная память запроса",
            "value": row[5] or "—",
            "role": "Макс. лимит",
        },
    ]

    sizes = {
        # Greenplum отображает параметр gp_vmem_protect_limit как число в МБ, в отличие от других параметров, значения которых обычно содержат единицу измерения.
        "gp_vmem_protect_limit": _parse_pg_size_to_bytes(row[0], default_unit="MB"),
        "shared_buffers": _parse_pg_size_to_bytes(row[1]),
        "work_mem": _parse_pg_size_to_bytes(row[2]),
        "maintenance_work_mem": _parse_pg_size_to_bytes(row[3]),
        "statement_mem": _parse_pg_size_to_bytes(row[4]),
        "max_statement_mem": _parse_pg_size_to_bytes(row[5]),
    }

    def usage_row(label, used_key, limit_key):
        """Формирует строку показателя использования памяти."""
        used = sizes.get(used_key)
        limit = sizes.get(limit_key)
        percent = round((used * 100 / limit), 2) if used is not None and limit else 0
        return {
            "label": label,
            "used": _format_bytes(used),
            "limit": _format_bytes(limit),
            "usage_percent": percent,
        }

    usage = [
        usage_row("Память запроса", "statement_mem", "max_statement_mem"),
        usage_row(
            "Максимальная память запроса", "max_statement_mem", "gp_vmem_protect_limit"
        ),
        usage_row("Память операций", "work_mem", "max_statement_mem"),
        usage_row("Кэш данных", "shared_buffers", "gp_vmem_protect_limit"),
    ]
    size_metrics = [
        {
            "key": "total",
            "label": "Общий размер БД",
            "size_bytes": int(row[6] or 0),
            "value": _format_bytes(int(row[6] or 0)),
        },
        {
            "key": "indexes",
            "label": "Размер индексов",
            "size_bytes": int(row[7] or 0),
            "value": _format_bytes(int(row[7] or 0)),
        },
        {
            "key": "data_without_indexes",
            "label": "Размер БД без индексов",
            "size_bytes": int(row[8] or 0),
            "value": _format_bytes(int(row[8] or 0)),
        },
        {
            "key": "temp_tables",
            "label": "Размер временных таблиц",
            "size_bytes": int(row[9] or 0),
            "value": _format_bytes(int(row[9] or 0)),
        },
        {
            "key": "materialized_views",
            "label": "Размер материализованных представлений",
            "size_bytes": int(row[10] or 0),
            "value": _format_bytes(int(row[10] or 0)),
        },
    ]
    return JsonResponse(
        {"ok": True, "settings": settings, "usage": usage, "size_metrics": size_metrics}
    )


@require_http_methods(["POST"])
def database_users_list(request):
    """Возвращает список пользователей выбранной базы данных."""
    return _database_roles_list(request, can_login=True)


@require_http_methods(["POST"])
def database_groups_list(request):
    """Возвращает список групп выбранной базы данных."""
    return _database_roles_list(request, can_login=False)


@require_http_methods(["POST"])
def maintenance_stats(request):
    """Возвращает статистику обслуживания таблиц базы данных."""
    payload = _read_json_body(request)
    db_connection, error_response = _require_payload_connection(request, payload)
    if error_response:
        return error_response
    page, page_size, offset, search, sort_column, direction = _list_query_params(
        payload,
        {
            "schema_name": "schemaname",
            "table_name": "relname",
            "live_rows": "live_rows",
            "dead_rows": "dead_rows",
            "dead_percent": "dead_percent",
            "last_vacuum": "last_vacuum_at",
            "last_analyze": "last_analyze_at",
        },
        "dead_rows",
    )
    where_sql = ""
    params = []
    if search:
        search_pattern = f"%{_escape_like_pattern(search)}%"
        where_sql = (
            "WHERE schemaname ILIKE %s ESCAPE '!' OR relname ILIKE %s ESCAPE '!'"
        )
        params.extend([search_pattern, search_pattern])

    maintenance_query = f"""
        WITH maintenance AS (
            SELECT
                schemaname,
                relname,
                COALESCE(n_live_tup, 0)::bigint AS live_rows,
                COALESCE(n_dead_tup, 0)::bigint AS dead_rows,
                CASE
                    WHEN COALESCE(n_live_tup, 0) + COALESCE(n_dead_tup, 0) = 0 THEN 0
                    ELSE ROUND(COALESCE(n_dead_tup, 0) * 100.0 / (COALESCE(n_live_tup, 0) + COALESCE(n_dead_tup, 0)), 2)
                END AS dead_percent,
                CASE
                    WHEN last_vacuum IS NULL THEN last_autovacuum
                    WHEN last_autovacuum IS NULL THEN last_vacuum
                    ELSE GREATEST(last_vacuum, last_autovacuum)
                END AS last_vacuum_at,
                CASE
                    WHEN last_analyze IS NULL THEN last_autoanalyze
                    WHEN last_autoanalyze IS NULL THEN last_analyze
                    ELSE GREATEST(last_analyze, last_autoanalyze)
                END AS last_analyze_at
            FROM pg_catalog.pg_stat_user_tables
        )
        SELECT
            schemaname,
            relname,
            live_rows,
            dead_rows,
            dead_percent,
            last_vacuum_at,
            last_analyze_at,
            COUNT(*) OVER() AS total_count
        FROM maintenance
        {where_sql}
        ORDER BY {sort_column} {direction}, schemaname ASC, relname ASC
        LIMIT %s OFFSET %s;
    """

    rows, error_response = _query_or_error(
        "Не удалось получить статистику обслуживания",
        lambda: _fetch_db_rows(db_connection, maintenance_query, [*params, page_size, offset]),
    )
    if error_response:
        return error_response

    def format_datetime(value):
        """Форматирует дату и время статистики обслуживания."""
        return value.strftime("%Y-%m-%d %H:%M:%S") if value else "Никогда"

    tables = [
        {
            "schema_name": row[0],
            "table_name": row[1],
            "live_rows": int(row[2] or 0),
            "dead_rows": int(row[3] or 0),
            "dead_percent": float(row[4] or 0),
            "last_vacuum": format_datetime(row[5]),
            "last_analyze": format_datetime(row[6]),
        }
        for row in rows
    ]
    total_count = int(rows[0][7]) if rows else 0
    return JsonResponse(
        {
            "ok": True,
            "tables": tables,
            "page": page,
            "page_size": page_size,
            "total_count": total_count,
        }
    )


@require_http_methods(["POST"])
def maintenance_operation(request):
    """Запускает фоновое обслуживание или возвращает состояние задачи."""
    permission_error = _destructive_action_permission_error(request)
    if permission_error:
        return permission_error
    db_user = _current_db_user(request)

    payload = _read_json_body(request)
    if payload.get("job_id"):
        job = MaintenanceJob.objects.select_related("connection", "user").filter(
            pk=payload["job_id"], user=db_user
        ).first()
        if not job:
            return JsonResponse(
                {"ok": False, "message": "Задача обслуживания не найдена"},
                status=404,
            )
        return JsonResponse({"ok": True, "job": _serialize_maintenance_job(job)})

    db_connection, error_response = _require_payload_connection(request, payload)
    if error_response:
        return error_response
    schema_name = str(payload.get("schema_name") or "").strip()
    table_name = str(payload.get("table_name") or "").strip()
    operation = str(payload.get("operation") or "vacuum").lower()
    if not schema_name or not table_name:
        return JsonResponse(
            {"ok": False, "message": "Не выбрана таблица для обслуживания"}, status=400
        )
    if operation not in {"vacuum", "vacuum_full", "analyze", "explain_analyze"}:
        return JsonResponse(
            {"ok": False, "message": "Неизвестная операция обслуживания"}, status=400
        )

    job = MaintenanceJob.objects.create(
        user=db_user,
        connection=db_connection,
        operation=operation,
        schema_name=schema_name,
        table_name=table_name,
    )
    _write_audit(
        operation,
        _maintenance_operation_audit_info(
            operation,
            db_connection,
            schema_name,
            table_name,
            "запущено в фоновом режиме",
        ),
        db_user=db_user,
    )
    _submit_maintenance_job(job.pk)
    return JsonResponse(
        {
            "ok": True,
            "job": _serialize_maintenance_job(job),
        },
        status=202,
    )


@require_http_methods(["GET", "POST"])
def maintenance_jobs(request):
    """Возвращает сохранённую историю фоновых задач текущего пользователя."""
    db_user = _current_db_user(request)
    if not db_user:
        return JsonResponse({"ok": False, "message": "Требуется вход в приложение"}, status=401)
    jobs = MaintenanceJob.objects.select_related("connection", "user").filter(user=db_user)[:25]
    return JsonResponse({"ok": True, "jobs": [_serialize_maintenance_job(job) for job in jobs]})
