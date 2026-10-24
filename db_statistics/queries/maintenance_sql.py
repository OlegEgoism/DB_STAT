"""Запросы обслуживания: завершение сессии и статистика таблицы после VACUUM/ANALYZE."""


def terminate_backend_sql(*, require_active):
    """Текст завершения процесса; require_active ограничивает только активными запросами."""
    active_clause = "\n          AND activity.state = 'active'" if require_active else ""
    return f"""
        SELECT
            pg_catalog.pg_terminate_backend(activity.pid),
            activity.pid,
            activity.usename,
            activity.datname,
            activity.application_name,
            activity.client_addr,
            activity.client_port,
            activity.state,
            activity.backend_type,
            activity.backend_start,
            activity.xact_start,
            activity.query_start,
            activity.state_change,
            activity.wait_event_type,
            activity.wait_event,
            now() - activity.backend_start AS session_duration,
            CASE WHEN activity.query_start IS NULL THEN NULL ELSE now() - activity.query_start END AS query_duration,
            activity.query
        FROM pg_catalog.pg_stat_activity AS activity
        WHERE activity.pid = %s
          AND activity.pid <> pg_backend_pid(){active_clause};
    """


TABLE_STATISTICS_SQL = """
                    SELECT
                        COALESCE(n_live_tup, 0)::bigint,
                        COALESCE(n_dead_tup, 0)::bigint,
                        last_vacuum,
                        last_autovacuum,
                        last_analyze,
                        last_autoanalyze
                    FROM pg_catalog.pg_stat_user_tables
                    WHERE schemaname = %s AND relname = %s
"""
