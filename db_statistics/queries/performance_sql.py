"""Запросы раздела «Производительность»: активные запросы, сессии, блокировки, простаивающие транзакции."""

ACTIVE_QUERIES_SQL = """
        WITH locked_relations AS (
            SELECT
                locks.pid,
                string_agg(
                    DISTINCT namespace.nspname || '.' || relation.relname,
                    ', ' ORDER BY namespace.nspname || '.' || relation.relname
                ) AS relation_name
            FROM pg_catalog.pg_locks AS locks
            JOIN pg_catalog.pg_class AS relation
                ON relation.oid = locks.relation
            JOIN pg_catalog.pg_namespace AS namespace
                ON namespace.oid = relation.relnamespace
            WHERE locks.relation IS NOT NULL
            GROUP BY locks.pid
        )
        SELECT
            activity.pid,
            activity.usename,
            COALESCE(locked_relations.relation_name, '—') AS relation_name,
            activity.state,
            GREATEST(now() - activity.query_start, INTERVAL '0 seconds') AS duration,
            activity.query
        FROM pg_catalog.pg_stat_activity AS activity
        LEFT JOIN locked_relations
            ON locked_relations.pid = activity.pid
        WHERE activity.state = 'active'
          AND activity.pid <> pg_backend_pid()
          AND (%s = '' OR activity.usename ILIKE %s ESCAPE '!')
        ORDER BY duration DESC;
"""


SESSIONS_SQL = """
        SELECT
            pid,
            usename,
            datname,
            application_name,
            client_addr,
            client_port,
            backend_start,
            xact_start,
            query_start,
            state_change,
            state,
            wait_event_type,
            wait_event,
            backend_type,
            now() - backend_start AS session_duration,
            CASE WHEN query_start IS NULL THEN NULL ELSE now() - query_start END AS query_duration,
            query
        FROM pg_catalog.pg_stat_activity
        WHERE (%s = '' OR usename ILIKE %s ESCAPE '!')
          AND (%s = '' OR state = %s)
        ORDER BY
            CASE WHEN state = 'active' THEN 0 ELSE 1 END,
            backend_start DESC;
"""


BLOCKING_LOCKS_SQL = """
        SELECT
            blocked.pid AS blocked_pid,
            blocked.usename AS blocked_user,
            now() - blocked.query_start AS blocked_duration,
            blocked.query AS blocked_query,
            blocker.pid AS blocker_pid,
            blocker.usename AS blocker_user,
            now() - blocker.query_start AS blocker_duration,
            blocker.query AS blocker_query
        FROM pg_catalog.pg_locks AS blocked_locks
        JOIN pg_catalog.pg_stat_activity AS blocked
            ON blocked.pid = blocked_locks.pid
        JOIN pg_catalog.pg_locks AS blocker_locks
            ON blocker_locks.locktype = blocked_locks.locktype
           AND blocker_locks.database IS NOT DISTINCT FROM blocked_locks.database
           AND blocker_locks.relation IS NOT DISTINCT FROM blocked_locks.relation
           AND blocker_locks.page IS NOT DISTINCT FROM blocked_locks.page
           AND blocker_locks.tuple IS NOT DISTINCT FROM blocked_locks.tuple
           AND blocker_locks.virtualxid IS NOT DISTINCT FROM blocked_locks.virtualxid
           AND blocker_locks.transactionid IS NOT DISTINCT FROM blocked_locks.transactionid
           AND blocker_locks.classid IS NOT DISTINCT FROM blocked_locks.classid
           AND blocker_locks.objid IS NOT DISTINCT FROM blocked_locks.objid
           AND blocker_locks.objsubid IS NOT DISTINCT FROM blocked_locks.objsubid
           AND blocker_locks.pid <> blocked_locks.pid
        JOIN pg_catalog.pg_stat_activity AS blocker
            ON blocker.pid = blocker_locks.pid
        WHERE NOT blocked_locks.granted
          AND blocker_locks.granted
          AND (%s = '' OR blocked.usename ILIKE %s ESCAPE '!')
          AND (%s = '' OR blocker.usename ILIKE %s ESCAPE '!');
"""


IDLE_TRANSACTIONS_SQL = """
        SELECT
            pid,
            usename,
            application_name,
            client_addr,
            state,
            now() - xact_start AS transaction_duration,
            now() - state_change AS idle_duration,
            query
        FROM pg_catalog.pg_stat_activity
        WHERE state = 'idle in transaction'
          AND (%s = '' OR usename ILIKE %s ESCAPE '!')
        ORDER BY xact_start;
"""
