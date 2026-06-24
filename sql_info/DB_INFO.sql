-- Конфигурация сегментов кластера
SELECT
  content AS "Сегмент",
  role AS "Роль",
  preferred_role AS "Предпочт. роль",
  mode AS "Режим",
  status AS "Статус",
  port AS "Порт",
  hostname AS "Хост",
  address AS "Адрес"
FROM pg_catalog.gp_segment_configuration
ORDER BY dbid ASC;


-- Здоровье кластера
SELECT
    'Здоровье кластера' as check_name,
    CASE
        WHEN COUNT(*) = SUM(CASE WHEN status = 'u' THEN 1 ELSE 0 END)
             AND COUNT(*) = SUM(CASE WHEN mode = 's' THEN 1 ELSE 0 END)
        THEN '? Все сегменты подняты и синхронизированы'
        WHEN COUNT(*) > SUM(CASE WHEN status = 'u' THEN 1 ELSE 0 END)
        THEN '? Есть проблемы: ' ||
             (COUNT(*) - SUM(CASE WHEN status = 'u' THEN 1 ELSE 0 END)) ||
             ' сегментов не подняты'
        ELSE '? Критические проблемы'
    END as status
FROM gp_segment_configuration
WHERE content != -1;


-- Инфорамция о сегментах
SELECT * FROM gp_segment_configuration;


-- Подробная инфорамция о сегментах
SELECT 'Общее количество сегментов' , COUNT(*)::numeric
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


-- Распределение строк по сегментам
SELECT
    gp_segment_id AS "Сегмент",
    count(*) AS "Строк"
FROM dd04_finance.dd04443_bal_raw_f0611  -- TODO
GROUP BY gp_segment_id
ORDER BY gp_segment_id;


-- Размер баз данных
SELECT
    datname AS database_name,
    pg_size_pretty(pg_database_size(datname)) AS size
FROM pg_database
ORDER BY pg_database_size(datname) DESC;


-- Размер таблиц на диске
SELECT
    sotdschemaname AS schema_name,
    sotdtablename AS table_name,
    pg_size_pretty(sotdsize) AS table_size
FROM gp_toolkit.gp_size_of_table_disk
ORDER BY sotdsize DESC
LIMIT 50;

-- Размер объектов БД
SELECT
    n.nspname AS schema_name,
    c.relname AS object_name,
    CASE c.relkind
        WHEN 'r' THEN 'table'
        WHEN 'i' THEN 'index'
        WHEN 'S' THEN 'sequence'
        WHEN 'v' THEN 'view'
        WHEN 'm' THEN 'materialized view'
        WHEN 'f' THEN 'foreign table'
        WHEN 'p' THEN 'partitioned table'
        ELSE c.relkind::text
    END AS object_type,
    pg_size_pretty(pg_relation_size(c.oid)) AS object_size
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname NOT IN ('pg_catalog', 'information_schema')
  AND n.nspname NOT LIKE 'pg_toast%'
ORDER BY pg_relation_size(c.oid) DESC;









-- Пользователи и resource group
SELECT
    rolname AS user_name,
    rsgname AS resource_group
FROM pg_roles r
LEFT JOIN pg_resgroup g ON r.rolresgroup = g.oid
ORDER BY rolname;

-- Проверка возраста транзакций
SELECT
    datname,
    age(datfrozenxid) AS xid_age
FROM pg_database
ORDER BY xid_age DESC;












-- Активные долгие запросы
SELECT pid, usename, now() - query_start AS duration, state, query
FROM pg_stat_activity
WHERE state <> 'idle'
ORDER BY duration DESC;

SELECT
    pid,
    usename,
    now() - query_start AS duration,
    state,
    query
FROM pg_stat_activity
WHERE state <> 'idle'
  AND query NOT LIKE 'START_REPLICATION%'
ORDER BY duration DESC;


SELECT
    pid,
    usename,
    application_name,
    state,
    wait_event_type,
    now() - query_start AS duration,
    query
FROM pg_stat_activity
WHERE backend_type IS DISTINCT FROM 'walsender'
ORDER BY duration DESC;


SELECT
    pid,
    usename,
    application_name,
    now() - query_start AS duration,
    query
FROM pg_stat_activity
WHERE backend_type IS DISTINCT FROM 'walsender'
ORDER BY duration DESC;

-- 3. Блокировки
SELECT * FROM gp_toolkit.gp_locks_on_relation;

-- 4. Перекос данных
SELECT * FROM gp_toolkit.gp_skew_coefficients
ORDER BY skccoeff DESC
LIMIT 20;

-- Таблицы без статистики
SELECT * FROM gp_toolkit.gp_stats_missing;



-- Фактический размер таблицы / ожидаемый размер таблицы исходя из количества данных
SELECT *
FROM gp_toolkit.gp_bloat_diag;