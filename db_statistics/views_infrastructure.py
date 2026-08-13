from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

from db_statistics.view_helpers import _fetch_db_row, _fetch_db_rows, _open_database_connection, _read_json_body, _require_payload_connection


@require_http_methods(["POST"])
def database_overview(request):
    """Возвращает основные показатели и размеры базы данных."""
    payload = _read_json_body(request)
    db_connection, error_response = _require_payload_connection(request, payload)
    if error_response:
        return error_response
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
            (SELECT COUNT(*) FROM pg_catalog.pg_roles WHERE NOT rolcanlogin)::bigint AS group_count,
            (SELECT COUNT(*) FROM pg_catalog.pg_stat_activity)::bigint AS current_connections,
            (SELECT setting::int FROM pg_catalog.pg_settings WHERE name = 'max_connections') AS max_connections,
            (
                SELECT ROUND(COUNT(*) * 100.0 / setting::int, 2)
                FROM pg_catalog.pg_stat_activity, pg_catalog.pg_settings
                WHERE name = 'max_connections'
                GROUP BY setting
            ) AS connection_usage_percent,
            pg_postmaster_start_time() AS server_started_at,
            date_trunc('second', now() - pg_postmaster_start_time()) AS server_uptime,
            current_setting('server_version', true) AS server_version,
            current_setting('server_encoding', true) AS server_encoding,
            current_setting('TimeZone', true) AS timezone,
            current_setting('superuser_reserved_connections', true) AS superuser_reserved_connections,
            current_setting('statement_timeout', true) AS statement_timeout,
            current_setting('lock_timeout', true) AS lock_timeout,
            current_setting('idle_in_transaction_session_timeout', true) AS idle_in_transaction_session_timeout,
            current_setting('default_transaction_isolation', true) AS default_transaction_isolation,
            current_setting('DateStyle', true) AS date_style,
            (SELECT COALESCE(xact_commit, 0)::bigint FROM pg_catalog.pg_stat_database WHERE datname = %s) AS xact_commit,
            (SELECT COALESCE(xact_rollback, 0)::bigint FROM pg_catalog.pg_stat_database WHERE datname = %s) AS xact_rollback,
            (
                SELECT ROUND(
                    COALESCE(xact_rollback, 0)::numeric /
                    NULLIF(COALESCE(xact_commit, 0) + COALESCE(xact_rollback, 0), 0) * 100,
                    2
                )
                FROM pg_catalog.pg_stat_database
                WHERE datname = %s
            ) AS rollback_percent,
            (
                SELECT ROUND(
                    COALESCE(blks_hit, 0)::numeric /
                    NULLIF(COALESCE(blks_hit, 0) + COALESCE(blks_read, 0), 0) * 100,
                    2
                )
                FROM pg_catalog.pg_stat_database
                WHERE datname = %s
            ) AS cache_hit_percent,
            (SELECT age(datfrozenxid)::bigint FROM pg_catalog.pg_database WHERE datname = %s) AS xid_age
        FROM relation_sizes;
    """

    extensions_query = """
        SELECT
            extension.extname,
            extension.extversion,
            namespace.nspname,
            COALESCE(description.description, '—') AS description
        FROM pg_catalog.pg_extension AS extension
        JOIN pg_catalog.pg_namespace AS namespace
            ON namespace.oid = extension.extnamespace
        LEFT JOIN pg_catalog.pg_description AS description
            ON description.objoid = extension.oid
           AND description.classoid = 'pg_catalog.pg_extension'::regclass
        ORDER BY extension.extname;
    """

    try:
        row = _fetch_db_row(
            db_connection,
            overview_query,
            [
                db_connection.database,
                db_connection.database,
                db_connection.database,
                db_connection.database,
                db_connection.database,
                db_connection.database,
                db_connection.database,
            ],
        )
        extension_rows = _fetch_db_rows(db_connection, extensions_query)
    except Exception as exc:
        return JsonResponse(
            {"ok": False, "message": f"Не удалось получить обзор БД: {exc}"}, status=400
        )

    installed_extensions = [
        {
            "name": extension_row[0] or "—",
            "version": extension_row[1] or "—",
            "schema": extension_row[2] or "—",
            "description": extension_row[3] or "—",
        }
        for extension_row in extension_rows
    ]

    metrics = [
        {"key": "total", "label": "Общий размер БД", "size_bytes": int(row[4] or 0)},
        {"key": "indexes", "label": "Размер индексов", "size_bytes": int(row[5] or 0)},
        {
            "key": "data_without_indexes",
            "label": "Размер БД без индексов",
            "size_bytes": int(row[6] or 0),
        },
        {
            "key": "temp_tables",
            "label": "Размер временных таблиц",
            "size_bytes": int(row[7] or 0),
        },
        {
            "key": "materialized_views",
            "label": "Размер материализованных представлений",
            "size_bytes": int(row[8] or 0),
        },
    ]
    memory_settings = [
        {
            "key": "statement_mem",
            "label": "Память на один запрос",
            "setting": "statement_mem",
            "value": row[1] or "—",
        },
        {
            "key": "max_statement_mem",
            "label": "Максимальная память на запрос",
            "setting": "max_statement_mem",
            "value": row[2] or "—",
        },
        {
            "key": "gp_vmem_protect_limit",
            "label": "Лимит виртуальной памяти сегмента",
            "setting": "gp_vmem_protect_limit",
            "value": row[3] or "—",
        },
    ]
    connection_info = [
        {"label": "Хост", "value": db_connection.host},
        {"label": "Порт", "value": db_connection.port},
    ]
    role_counts = [
        {"label": "Пользователи", "count": int(row[9] or 0)},
        {"label": "Группы", "count": int(row[10] or 0)},
    ]
    connection_slots = [
        {
            "key": "current_connections",
            "label": "Текущие подключения",
            "value": int(row[11] or 0),
        },
        {
            "key": "max_connections",
            "label": "Максимум подключений",
            "value": int(row[12] or 0),
        },
        {
            "key": "usage_percent",
            "label": "Использование",
            "value": float(row[13] or 0),
        },
    ]
    transaction_total = int(row[25] or 0) + int(row[26] or 0)
    activity_stats = [
        {"key": "xact_commit", "label": "Коммитов", "value": int(row[25] or 0)},
        {"key": "xact_rollback", "label": "Роллбеков", "value": int(row[26] or 0)},
        {
            "key": "total_transactions",
            "label": "Всего транзакций",
            "value": transaction_total,
        },
        {
            "key": "rollback_percent",
            "label": "Откат (Rollback), %",
            "value": f"{float(row[27] or 0):.2f}%",
        },
        {
            "key": "cache_hit_percent",
            "label": "Доля попаданий в кэш",
            "value": f"{float(row[28] or 0):.2f}%",
        },
        {
            "key": "xid_age",
            "label": "Возраст транзакций (XID)",
            "value": int(row[29] or 0),
        },
    ]
    basic_settings = [
        {"key": "host", "label": "Хост", "value": db_connection.host},
        {"key": "port", "label": "Порт", "value": db_connection.port},
        {
            "key": "server_uptime",
            "label": "Время работы БД",
            "value": str(row[15]) if row[15] else "—",
        },
        {
            "key": "server_started_at",
            "label": "Запущена",
            "value": row[14].strftime("%Y-%m-%d %H:%M:%S") if row[14] else "—",
        },
        {"key": "server_version", "label": "Версия сервера", "value": row[16] or "—"},
        {
            "key": "server_encoding",
            "label": "Кодировка сервера",
            "value": row[17] or "—",
        },
        {"key": "timezone", "label": "Часовой пояс", "value": row[18] or "—"},
        {
            "key": "superuser_reserved_connections",
            "label": "Резерв подключений суперпользователя",
            "value": row[19] or "—",
        },
        {
            "key": "statement_timeout",
            "label": "Таймаут запроса",
            "value": row[20] or "—",
        },
        {
            "key": "lock_timeout",
            "label": "Таймаут ожидания блокировки",
            "value": row[21] or "—",
        },
        {
            "key": "idle_in_transaction_session_timeout",
            "label": "Таймаут простоя в транзакции",
            "value": row[22] or "—",
        },
        {
            "key": "default_transaction_isolation",
            "label": "Уровень изоляции по умолчанию",
            "value": row[23] or "—",
        },
        {"key": "date_style", "label": "Формат даты", "value": row[24] or "—"},
    ]
    return JsonResponse(
        {
            "ok": True,
            "database": db_connection.database,
            "database_version": row[0] or "—",
            "connection_info": connection_info,
            "metrics": metrics,
            "memory_settings": memory_settings,
            "role_counts": role_counts,
            "connection_slots": connection_slots,
            "activity_stats": activity_stats,
            "basic_settings": basic_settings,
            "installed_extensions": installed_extensions,
        }
    )


@require_http_methods(["POST"])
def segments_info(request):
    """Возвращает состояние и конфигурацию сегментов Greenplum."""
    payload = _read_json_body(request)
    db_connection, error_response = _require_payload_connection(request, payload)
    if error_response:
        return error_response
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
        with _open_database_connection(db_connection) as connection:
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
                metrics = [
                    {"name": row[0], "value": float(row[1])}
                    for row in cursor.fetchall()
                ]
    except Exception as exc:
        return JsonResponse(
            {
                "ok": False,
                "message": f"Не удалось получить информацию о сегментах: {exc}",
            },
            status=400,
        )

    return JsonResponse(
        {
            "ok": True,
            "segments": segments,
            "health": health_row[1] if health_row else "Нет данных",
            "metrics": metrics,
        }
    )
