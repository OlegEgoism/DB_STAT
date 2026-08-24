import uuid
from datetime import UTC, datetime

from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

from db_statistics.view_helpers import (
    EXCLUDED_SYSTEM_SCHEMAS_SQL,
    _current_db_user,
    _database_roles_list,
    _destructive_action_permission_error,
    _escape_like_pattern,
    _evict_stale_maintenance_jobs,
    _fetch_db_row,
    _fetch_db_rows,
    _format_bytes,
    _list_query_params,
    _maintenance_vacuum_audit_info,
    _parse_pg_size_to_bytes,
    _read_json_body,
    _require_payload_connection,
    _run_maintenance_vacuum,
    _safe_db_error_message,
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

    try:
        row = _fetch_db_row(
            db_connection,
            memory_query,
            [db_connection.database, db_connection.database],
        )
    except Exception as exc:
        return JsonResponse(
            {
                "ok": False,
                "message": _safe_db_error_message(
                    "Не удалось получить параметры памяти", exc
                ),
            },
            status=400,
        )

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
def runtime_memory_usage(request):
    """Возвращает фактическое потребление RAM resource groups в Greenplum.

    ``memory_usage`` берётся из cgroups на каждом segment host. Greenplum не
    публикует RSS отдельного пользователя в SQL, поэтому пользовательская
    детализация честно показывает общий RSS его группы и число активных
    запросов, а не приписывает разделяемую память конкретному backend.
    """
    payload = _read_json_body(request)
    db_connection, error_response = _require_payload_connection(request, payload)
    if error_response:
        return error_response

    host_query = """
        SELECT
            status.groupid,
            status.groupname,
            status.hostname,
            COALESCE(status.cpu_usage, 0),
            COALESCE(status.memory_usage, 0),
            config.memory_quota,
            config.concurrency
        FROM gp_toolkit.gp_resgroup_status_per_host AS status
        LEFT JOIN gp_toolkit.gp_resgroup_config AS config
            ON config.groupid = status.groupid
        ORDER BY status.memory_usage DESC, status.groupname, status.hostname;
    """
    users_query = """
        WITH active_users AS (
            SELECT
                activity.usename,
                roles.rolresgroup AS groupid,
                COUNT(*) FILTER (WHERE activity.state = 'active')::integer AS active_queries,
                COUNT(*)::integer AS sessions
            FROM pg_catalog.pg_stat_activity AS activity
            JOIN pg_catalog.pg_roles AS roles ON roles.rolname = activity.usename
            WHERE activity.usename IS NOT NULL
              AND activity.pid <> pg_backend_pid()
            GROUP BY activity.usename, roles.rolresgroup
        ), group_memory AS (
            SELECT groupid, groupname, SUM(COALESCE(memory_usage, 0)) AS memory_usage
            FROM gp_toolkit.gp_resgroup_status_per_host
            GROUP BY groupid, groupname
        )
        SELECT
            users.usename,
            COALESCE(memory.groupname, '—'),
            users.active_queries,
            users.sessions,
            COALESCE(memory.memory_usage, 0)
        FROM active_users AS users
        LEFT JOIN group_memory AS memory ON memory.groupid = users.groupid
        ORDER BY users.active_queries DESC, memory.memory_usage DESC, users.usename;
    """
    status_query = """
        SELECT groupid, groupname, num_running, num_queueing
        FROM gp_toolkit.gp_resgroup_status;
    """
    # smaps_rollup даёт PSS (пропорциональную долю разделяемых страниц) и Swap
    # каждого QE-процесса. В отличие от RSS resource group это позволяет
    # привязать физическую память к конкретной Greenplum session/query.
    query_process_memory_sql = """
        WITH process_samples AS (
            SELECT
                activity.gp_segment_id AS segment_id,
                activity.sess_id,
                activity.pid,
                activity.usename,
                activity.datname,
                activity.query,
                pg_catalog.pg_read_file(
                    '/proc/' || activity.pid::text || '/smaps_rollup',
                    0,
                    1048576,
                    true
                ) AS smaps
            FROM gp_dist_random('pg_stat_activity') AS activity
            WHERE activity.state = 'active'
              AND activity.usename IS NOT NULL
              AND activity.pid <> pg_backend_pid()
        ), parsed AS (
            SELECT
                *,
                COALESCE(substring(smaps FROM 'Pss:\\s+([0-9]+) kB')::bigint, 0) AS pss_kb,
                COALESCE(substring(smaps FROM 'SwapPss:\\s+([0-9]+) kB')::bigint, 0) AS swap_kb
            FROM process_samples
            WHERE smaps IS NOT NULL
        )
        SELECT
            sess_id,
            usename,
            datname,
            COUNT(*)::integer AS process_count,
            COUNT(DISTINCT segment_id)::integer AS segment_count,
            SUM(pss_kb)::bigint AS pss_kb,
            SUM(swap_kb)::bigint AS swap_kb,
            MIN(query) AS query
        FROM parsed
        GROUP BY sess_id, usename, datname
        ORDER BY SUM(pss_kb) DESC, SUM(swap_kb) DESC;
    """

    try:
        host_rows = _fetch_db_rows(db_connection, host_query)
        user_rows = _fetch_db_rows(db_connection, users_query)
        status_rows = _fetch_db_rows(db_connection, status_query)
    except Exception as exc:
        return JsonResponse(
            {
                "ok": False,
                "message": _safe_db_error_message(
                    "Не удалось получить фактическое использование RAM resource groups. Представление доступно только в Greenplum с активными resource groups",
                    exc,
                ),
            },
            status=400,
        )

    process_rows = []
    process_warning = ""
    try:
        process_rows = _fetch_db_rows(db_connection, query_process_memory_sql)
    except Exception as exc:
        process_warning = _safe_db_error_message(
            "Не удалось прочитать RAM и Swap процессов запросов. Подключению нужны права на pg_read_file и чтение /proc/<pid>/smaps_rollup на segment hosts",
            exc,
        )

    statuses = {row[0]: row for row in status_rows}
    groups = []
    total_memory_mb = 0.0
    for row in host_rows:
        memory_mb = float(row[4] or 0)
        total_memory_mb += memory_mb
        status = statuses.get(row[0], ())
        groups.append(
            {
                "group_id": row[0],
                "group_name": row[1] or "—",
                "hostname": row[2] or "—",
                "cpu_usage": float(row[3] or 0),
                "memory_mb": memory_mb,
                "memory": _format_bytes(int(memory_mb * 1024 * 1024)),
                "memory_quota": row[5] if row[5] is not None else "—",
                "concurrency": row[6] if row[6] is not None else "—",
                "running": status[2] if len(status) > 2 else 0,
                "queueing": status[3] if len(status) > 3 else 0,
            }
        )

    users = [
        {
            "username": row[0] or "—",
            "group_name": row[1] or "—",
            "active_queries": row[2] or 0,
            "sessions": row[3] or 0,
            "shared_group_memory_mb": float(row[4] or 0),
            "shared_group_memory": _format_bytes(int(float(row[4] or 0) * 1024 * 1024)),
        }
        for row in user_rows
    ]
    queries = []
    for row in process_rows:
        pss_bytes = int(row[5] or 0) * 1024
        swap_bytes = int(row[6] or 0) * 1024
        queries.append(
            {
                "session_id": row[0],
                "username": row[1] or "—",
                "database": row[2] or "—",
                "process_count": row[3] or 0,
                "segment_count": row[4] or 0,
                "ram_bytes": pss_bytes,
                "ram": _format_bytes(pss_bytes),
                "swap_bytes": swap_bytes,
                "swap": _format_bytes(swap_bytes),
                "query": row[7] or "—",
            }
        )
    return JsonResponse(
        {
            "ok": True,
            "groups": groups,
            "users": users,
            "queries": queries,
            "process_warning": process_warning,
            "total_memory_mb": total_memory_mb,
            "total_memory": _format_bytes(int(total_memory_mb * 1024 * 1024)),
            "measurement": "Фактический RSS resource group из Linux cgroups, суммированный по segment hosts",
            "sampled_at": datetime.now(UTC).isoformat(),
        }
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

    try:
        rows = _fetch_db_rows(
            db_connection, maintenance_query, [*params, page_size, offset]
        )
    except Exception as exc:
        return JsonResponse(
            {
                "ok": False,
                "message": _safe_db_error_message(
                    "Не удалось получить статистику обслуживания", exc
                ),
            },
            status=400,
        )

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
def maintenance_vacuum(request):
    """Запускает VACUUM или возвращает состояние фоновой задачи."""
    permission_error = _destructive_action_permission_error(request)
    if permission_error:
        return permission_error
    db_user = _current_db_user(request)

    payload = _read_json_body(request)
    if payload.get("job_id"):
        with settings.MAINTENANCE_JOBS_LOCK:
            _evict_stale_maintenance_jobs()
            job_id = str(payload["job_id"])
            job = settings.MAINTENANCE_JOBS.get(job_id)
            if not job or job["user_id"] != db_user.pk:
                return JsonResponse(
                    {"ok": False, "message": "Задача обслуживания не найдена"},
                    status=404,
                )
            response_job = {
                key: value for key, value in job.items() if key != "user_id"
            }
            if job["status"] != "running":
                settings.MAINTENANCE_JOBS.pop(job_id, None)
            return JsonResponse({"ok": True, "job": response_job})

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
    if operation not in {"vacuum", "vacuum_full"}:
        return JsonResponse(
            {"ok": False, "message": "Неизвестная операция обслуживания"}, status=400
        )

    job_id = uuid.uuid4().hex
    job = {
        "id": job_id,
        "user_id": db_user.pk,
        "status": "running",
        "operation": operation,
        "schema_name": schema_name,
        "table_name": table_name,
        "message": "Операция выполняется",
    }
    with settings.MAINTENANCE_JOBS_LOCK:
        _evict_stale_maintenance_jobs()
        settings.MAINTENANCE_JOBS[job_id] = job
    _write_audit(
        operation,
        _maintenance_vacuum_audit_info(
            operation,
            db_connection,
            schema_name,
            table_name,
            "запущено в фоновом режиме",
        ),
        db_user=db_user,
    )
    settings.MAINTENANCE_JOB_EXECUTOR.submit(
        _run_maintenance_vacuum,
        job_id,
        db_connection.pk,
        schema_name,
        table_name,
        operation,
        db_user.login,
    )
    return JsonResponse(
        {
            "ok": True,
            "job": {key: value for key, value in job.items() if key != "user_id"},
        },
        status=202,
    )
