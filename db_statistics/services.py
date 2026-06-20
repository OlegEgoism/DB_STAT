from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import psycopg2
from psycopg2.extras import RealDictCursor

from db_statistics.models import DBConnection

SEGMENT_CONFIGURATION_SQL = """
SELECT
  content AS "Сегмент",
  role AS "Роль",
  preferred_role AS "Предпочт. роль",
  mode AS "Режим",
  status AS "Статус",
  port AS "Порт",
  hostname AS "Хост",
  address AS "Адрес",
  datadir AS "Директория"
FROM pg_catalog.gp_segment_configuration
ORDER BY dbid ASC;
"""

CLUSTER_HEALTH_SQL = """
SELECT
    'Здоровье кластера' as check_name,
    CASE
        WHEN COUNT(*) = SUM(CASE WHEN status = 'u' THEN 1 ELSE 0 END)
             AND COUNT(*) = SUM(CASE WHEN mode = 's' THEN 1 ELSE 0 END)
        THEN '✅ Все сегменты подняты и синхронизированы'
        WHEN COUNT(*) > SUM(CASE WHEN status = 'u' THEN 1 ELSE 0 END)
        THEN '⚠️ Есть проблемы: ' ||
             (COUNT(*) - SUM(CASE WHEN status = 'u' THEN 1 ELSE 0 END)) ||
             ' сегментов не подняты'
        ELSE '❌ Критические проблемы'
    END as status
FROM gp_segment_configuration
WHERE content != -1;
"""

SEGMENT_DETAILS_SQL = """
SELECT 'Общее количество сегментов' AS metric, COUNT(*)::text AS value
FROM gp_segment_configuration
WHERE content >= 0
UNION ALL
SELECT 'Cегменты работают', COUNT(*) FILTER (WHERE status = 'u')::text
FROM gp_segment_configuration
WHERE content >= 0
UNION ALL
SELECT 'Cегменты не работают', COUNT(*) FILTER (WHERE status = 'd')::text
FROM gp_segment_configuration
WHERE content >= 0
UNION ALL
SELECT 'Cинхронизированные сегменты', COUNT(*) FILTER (WHERE mode = 's')::text
FROM gp_segment_configuration
WHERE content >= 0
UNION ALL
SELECT 'Основные сегменты', COUNT(*) FILTER (WHERE role = 'p')::text
FROM gp_segment_configuration
WHERE content >= 0
UNION ALL
SELECT 'Зеркальные сегменты', COUNT(*) FILTER (WHERE role = 'm')::text
FROM gp_segment_configuration
WHERE content >= 0
UNION ALL
SELECT 'Процент здоровья', ROUND(100.0 * COUNT(*) FILTER (WHERE status = 'u') / NULLIF(COUNT(*), 0))::text
FROM gp_segment_configuration
WHERE content >= 0;
"""

POSTGRES_HEALTH_SQL = """
SELECT
    'Состояние PostgreSQL' AS check_name,
    '✅ Подключение установлено, сервер отвечает' AS status;
"""

POSTGRES_DETAILS_SQL = """
SELECT 'Активные подключения к текущей БД' AS metric, COUNT(*)::text AS value
FROM pg_stat_activity
WHERE datname = current_database()
UNION ALL
SELECT 'Размер текущей БД', pg_size_pretty(pg_database_size(current_database()))
UNION ALL
SELECT 'Всего баз данных', COUNT(*)::text
FROM pg_database
UNION ALL
SELECT 'Версия сервера', current_setting('server_version')
UNION ALL
SELECT 'Максимум подключений', current_setting('max_connections');
"""

POSTGRES_CONFIGURATION_SQL = """
SELECT
    datname AS "База данных",
    pg_catalog.pg_get_userbyid(datdba) AS "Владелец",
    pg_catalog.pg_encoding_to_char(encoding) AS "Кодировка",
    datcollate AS "Collate",
    datctype AS "Ctype",
    pg_catalog.pg_size_pretty(pg_catalog.pg_database_size(datname)) AS "Размер",
    datallowconn AS "Разрешены подключения"
FROM pg_catalog.pg_database
ORDER BY datname;
"""

HAS_GREENPLUM_SEGMENTS_SQL = """
SELECT to_regclass('pg_catalog.gp_segment_configuration') IS NOT NULL AS has_segments;
"""


@dataclass
class SegmentDashboardData:
    configuration: list[dict[str, Any]]
    health: dict[str, Any] | None
    details: list[dict[str, Any]]
    title: str = "Состояние кластера"
    table_title: str = "Конфигурация сегментов"
    error: str | None = None


def _fetch_all(cursor: RealDictCursor, query: str) -> list[dict[str, Any]]:
    cursor.execute(query)
    return [dict(row) for row in cursor.fetchall()]


def load_segment_dashboard(connection: DBConnection) -> SegmentDashboardData:
    """Загружает данные о сегментах Greenplum по сохраненному подключению."""

    try:
        with psycopg2.connect(
            host=connection.host,
            port=connection.port,
            dbname=connection.database,
            user=connection.username,
            password=connection.password,
            connect_timeout=5,
        ) as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(HAS_GREENPLUM_SEGMENTS_SQL)
                has_segments = cursor.fetchone()["has_segments"]

                if has_segments:
                    configuration = _fetch_all(cursor, SEGMENT_CONFIGURATION_SQL)
                    health_rows = _fetch_all(cursor, CLUSTER_HEALTH_SQL)
                    details = _fetch_all(cursor, SEGMENT_DETAILS_SQL)
                    title = "Состояние кластера"
                    table_title = "Конфигурация сегментов"
                else:
                    configuration = _fetch_all(cursor, POSTGRES_CONFIGURATION_SQL)
                    health_rows = _fetch_all(cursor, POSTGRES_HEALTH_SQL)
                    details = _fetch_all(cursor, POSTGRES_DETAILS_SQL)
                    title = "Доступная информация PostgreSQL"
                    table_title = "Базы данных"
    except psycopg2.Error as exc:
        return SegmentDashboardData(configuration=[], health=None, details=[], error=str(exc).strip())

    return SegmentDashboardData(
        configuration=configuration,
        health=health_rows[0] if health_rows else None,
        details=details,
        title=title,
        table_title=table_title,
    )
