"""Запросы раздела «Инфраструктура»: обзор БД, расширения, конфигурация, сегменты Greenplum."""

from db_statistics.queries.common import EXCLUDED_SYSTEM_SCHEMAS_SQL

EXTENSIONS_SQL = """
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


CONFIG_SQL = """
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


HEALTH_SQL = """
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


METRICS_SQL = """
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


def overview_sql():
    """Текст запроса: значения передаются параметрами, не подставляются в текст."""
    return f"""
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
