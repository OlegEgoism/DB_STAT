import psycopg2
from django.utils import timezone

from db_statistics.models import DBAudit

SEGMENT_CONFIG_QUERY = """
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

SEGMENT_HEALTH_QUERY = """
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

SEGMENT_METRICS_QUERY = """
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


def load_segments_health(db_connection, connection_kwargs_factory):
    with psycopg2.connect(
        **connection_kwargs_factory(
            db_connection.host,
            db_connection.port,
            db_connection.database,
            db_connection.username,
            db_connection.get_password(),
        )
    ) as connection:
        with connection.cursor() as cursor:
            cursor.execute(SEGMENT_CONFIG_QUERY)
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
            cursor.execute(SEGMENT_HEALTH_QUERY)
            health_row = cursor.fetchone()
            cursor.execute(SEGMENT_METRICS_QUERY)
            metrics = [{"name": row[0], "value": float(row[1])} for row in cursor.fetchall()]
    return {"segments": segments, "health": health_row[1] if health_row else "Нет данных", "metrics": metrics}


def write_segment_health_audit(db_connection, result=None, error=None, username="Фоновая задача"):
    metrics = result.get("metrics", []) if result else []
    metric_text = "; ".join(f"{item['name']}: {item['value']:g}" for item in metrics)
    details = [
        "Действие: Фоновый запрос Состояние сегментов",
        f"Подключение: {db_connection.name}",
        f"Хост: {db_connection.host}",
        f"Порт: {db_connection.port}",
        f"База данных: {db_connection.database}",
        f"Пользователь БД: {db_connection.username}",
    ]
    if result:
        details.extend([f"Результат: Успешно", f"Здоровье: {result['health']}"])
        if metric_text:
            details.append(f"Метрики: {metric_text}")
    if error:
        details.extend(["Результат: Ошибка", f"Ошибка: {error}"])
    DBAudit.objects.create(username=username, action_type="segment_health_check", info="; ".join(details), created=timezone.now())
