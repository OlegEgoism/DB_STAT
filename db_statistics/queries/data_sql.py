"""SQL-запросы раздела «Данные» (таблицы, схемы, представления, функции, временные и TOAST-таблицы).

Вынесены из views/data.py, чтобы представление отвечало только за разбор запроса и
ответ. Значения пользователя в текст не подставляются: поиск и избранное передаются
через where_sql с параметрами psycopg2, сортировка — через белый список колонок.
"""

from psycopg2 import sql

from db_statistics.queries.common import EXCLUDED_SYSTEM_SCHEMAS_SQL

VALIDATE_SQL = """
        SELECT 1
        FROM pg_catalog.pg_class AS table_class
        JOIN pg_catalog.pg_namespace AS namespace
            ON namespace.oid = table_class.relnamespace
        WHERE namespace.nspname = %s
          AND table_class.relname = %s
          AND table_class.relkind IN ('r', 'p', 'm')
        LIMIT 1;
"""


def schema_sizes_sql(*, direction, sort_column, where_sql):
    """Текст запроса для раздела «Данные»."""
    return f"""
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


def schema_distribution_sql(*, where_sql):
    """Текст запроса для раздела «Данные»."""
    return f"""
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


def table_sizes_sql(*, direction, sort_column, where_sql):
    """Текст запроса для раздела «Данные»."""
    return f"""
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


def table_distribution_sql(*, where_sql):
    """Текст запроса для раздела «Данные»."""
    return f"""
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


def views_sql(*, direction, sort_column, type_sql, where_sql):
    """Текст запроса для раздела «Данные»."""
    return f"""
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


def functions_sql(*, direction, sort_column, where_sql):
    """Текст запроса для раздела «Данные»."""
    return f"""
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


def tables_sql():
    """Текст запроса для раздела «Данные»."""
    return f"""
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


def temp_table_sizes_sql(*, direction, sort_column, where_sql):
    """Текст запроса для раздела «Данные»."""
    return f"""
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


def temp_table_distribution_sql(*, where_sql):
    """Текст запроса для раздела «Данные»."""
    return f"""
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


def toast_tables_sql(*, direction, sort_column, where_sql):
    """Текст запроса для раздела «Данные»."""
    return f"""
        WITH toast_tables AS (
            SELECT
                parent_namespace.nspname AS schema_name,
                parent.relname AS table_name,
                toast.relname AS toast_table_name,
                pg_relation_size(toast.oid)::bigint AS toast_bytes,
                pg_indexes_size(toast.oid)::bigint AS toast_index_bytes,
                pg_total_relation_size(toast.oid)::bigint AS toast_total_bytes,
                pg_relation_size(parent.oid)::bigint AS heap_bytes,
                pg_total_relation_size(parent.oid)::bigint AS total_bytes,
                COALESCE(stat.n_live_tup, 0)::bigint AS live_chunks,
                COALESCE(stat.n_dead_tup, 0)::bigint AS dead_chunks
            FROM pg_catalog.pg_class AS parent
            JOIN pg_catalog.pg_namespace AS parent_namespace
                ON parent_namespace.oid = parent.relnamespace
            JOIN pg_catalog.pg_class AS toast
                ON toast.oid = parent.reltoastrelid
            LEFT JOIN pg_catalog.pg_stat_all_tables AS stat
                ON stat.relid = toast.oid
            WHERE parent.relkind IN ('r', 'm')
              AND parent.reltoastrelid <> 0
              AND parent_namespace.nspname NOT IN {EXCLUDED_SYSTEM_SCHEMAS_SQL}
              AND parent_namespace.nspname NOT LIKE 'pg_toast%%'
              AND parent_namespace.nspname NOT LIKE 'pg_temp_%%'
              AND pg_relation_size(toast.oid) > 0
              {where_sql}
        )
        SELECT
            schema_name,
            table_name,
            toast_table_name,
            toast_bytes,
            toast_index_bytes,
            toast_total_bytes,
            pg_size_pretty(toast_total_bytes) AS toast_total_size,
            pg_size_pretty(heap_bytes) AS heap_size,
            heap_bytes,
            COALESCE(ROUND(100.0 * toast_total_bytes / NULLIF(total_bytes, 0), 1), 0)::float AS toast_share,
            live_chunks,
            dead_chunks,
            COUNT(*) OVER() AS total_count,
            SUM(toast_total_bytes) OVER()::bigint AS all_toast_bytes,
            pg_size_pretty(SUM(toast_total_bytes) OVER()::bigint) AS all_toast_size
        FROM toast_tables
        ORDER BY {sort_column} {direction}, schema_name ASC, table_name ASC
        LIMIT %s OFFSET %s;
    """


TEMP_TABLE_EXISTS_SQL = """
                    SELECT 1
                    FROM pg_catalog.pg_class AS table_class
                    JOIN pg_catalog.pg_namespace AS namespace
                        ON namespace.oid = table_class.relnamespace
                    WHERE namespace.nspname = %s
                      AND table_class.relname = %s
                      AND table_class.relkind IN ('r', 'p')
                      AND (table_class.relpersistence = 't' OR namespace.nspname LIKE 'pg_temp_%%');
"""


def segment_distribution_sql(schema_name, table_name):
    """Количество строк таблицы по сегментам Greenplum (идентификаторы экранируются psycopg2.sql)."""
    return sql.SQL("""
        SELECT gp_segment_id::int AS segment_id, COUNT(*)::bigint AS row_count
        FROM {}.{}
        GROUP BY gp_segment_id
        ORDER BY gp_segment_id ASC;
    """).format(sql.Identifier(schema_name), sql.Identifier(table_name))
