"""Запросы раздела «Администрирование»: память, обслуживание и роли БД."""

from db_statistics.queries.common import EXCLUDED_SYSTEM_SCHEMAS_SQL


def memory_sql():
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


def maintenance_sql(*, direction, sort_column, where_sql):
    """Текст запроса: значения передаются параметрами, не подставляются в текст."""
    return f"""
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


def roles_sql(*, direction, sort_column, where_sql):
    """Текст запроса: значения передаются параметрами, не подставляются в текст."""
    return f"""
        WITH roles AS (
            SELECT
                role_info.rolname AS name,
                role_info.rolsuper AS superuser,
                role_info.rolcreatedb AS createdb,
                role_info.rolcreaterole AS createrole,
                role_info.rolinherit AS inherit,
                role_info.rolreplication AS replication,
                role_info.rolconnlimit AS connection_limit,
                role_info.rolvaliduntil AS valid_until,
                COUNT(membership.member)::bigint AS member_count
            FROM pg_catalog.pg_roles AS role_info
            LEFT JOIN pg_catalog.pg_auth_members AS membership
                ON membership.roleid = role_info.oid
            WHERE role_info.rolcanlogin = %s
              {where_sql}
            GROUP BY
                role_info.rolname,
                role_info.rolsuper,
                role_info.rolcreatedb,
                role_info.rolcreaterole,
                role_info.rolinherit,
                role_info.rolreplication,
                role_info.rolconnlimit,
                role_info.rolvaliduntil
        )
        SELECT
            name,
            superuser,
            createdb,
            createrole,
            inherit,
            replication,
            connection_limit,
            valid_until,
            member_count,
            COUNT(*) OVER() AS total_count,
            SUM(CASE WHEN superuser THEN 1 ELSE 0 END) OVER() AS superuser_count,
            SUM(CASE WHEN createdb THEN 1 ELSE 0 END) OVER() AS createdb_count,
            SUM(CASE WHEN replication THEN 1 ELSE 0 END) OVER() AS replication_count,
            SUM(CASE WHEN superuser OR createdb OR createrole OR replication THEN 1 ELSE 0 END) OVER() AS privileged_count
        FROM roles
        ORDER BY {sort_column} {direction}, name ASC
        LIMIT %s OFFSET %s;
    """
