import psycopg2
from psycopg2.extras import RealDictCursor


class DatabaseInspectionError(Exception):
    pass


def inspect_database(connection_settings):
    try:
        with psycopg2.connect(host=connection_settings.host, port=connection_settings.port, dbname=connection_settings.database, user=connection_settings.username, password=connection_settings.password, connect_timeout=5) as connection:
            with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("select version() as version, current_database() as database_name, current_user as user_name")
                overview = cursor.fetchone()

                cursor.execute(
                    """
                    select schema_name
                    from information_schema.schemata
                    where schema_name not in ('pg_catalog', 'information_schema')
                    order by schema_name
                    """
                )
                schemas = cursor.fetchall()

                cursor.execute(
                    """
                    select table_schema, table_name, table_type
                    from information_schema.tables
                    where table_schema not in ('pg_catalog', 'information_schema')
                    order by table_schema, table_name
                    limit 200
                    """
                )
                tables = cursor.fetchall()

                cursor.execute(
                    """
                    select table_schema, table_name, count(*) as columns_count
                    from information_schema.columns
                    where table_schema not in ('pg_catalog', 'information_schema')
                    group by table_schema, table_name
                    order by table_schema, table_name
                    limit 200
                    """
                )
                columns = cursor.fetchall()
    except psycopg2.Error as exc:
        raise DatabaseInspectionError(str(exc).strip()) from exc

    return {"overview": overview, "schemas": schemas, "tables": tables, "columns": columns}
