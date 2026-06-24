-- Размеры по схемам
SELECT
    n.nspname AS "Схема",
    pg_size_pretty(SUM(pg_relation_size(c.oid))) AS "Суммарно",
    pg_size_pretty(SUM(pg_total_relation_size(c.oid))) AS "Итого с индексами/TOAST"
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE
    c.relkind='r' AND n.nspname NOT IN ('pg_catalog','information_schema')
GROUP BY n.nspname
ORDER BY SUM(pg_total_relation_size(c.oid)) DESC;


-- Размер таблиц на диске
SELECT
    sotdschemaname AS schema_name,
    sotdtablename AS table_name,
    pg_size_pretty(sotdsize) AS table_size
FROM gp_toolkit.gp_size_of_table_disk
ORDER BY sotdsize DESC
LIMIT 50;


-- Размер текущей БД
SELECT pg_size_pretty(pg_database_size(current_database())) AS "Размер текущей БД";  -- 1453 GB


-- Суммарный размер временных таблиц
SELECT
    pg_size_pretty(SUM(pg_total_relation_size(c.oid))) AS "Размер временных таблиц"
FROM pg_catalog.pg_class c
JOIN pg_catalog.pg_namespace n ON c.relnamespace = n.oid
WHERE n.nspname NOT IN ('pg_catalog', 'information_schema')
    AND c.relkind = 'r'
    AND c.relname NOT LIKE 'pg_%'
    AND c.relname NOT LIKE 'sql_%'
    AND c.relpersistence = 't';


-- Таблиц с детализацией по форкам
SELECT
    n.nspname AS "Схема",
    c.relname AS "Таблица",
    (SELECT count(*) FROM pg_index i WHERE i.indrelid = c.oid) AS "Кол-во индексов",
    pg_size_pretty(pg_total_relation_size(c.oid)) AS "Общий размер",
    pg_size_pretty(pg_relation_size(c.oid, 'main')) AS "Heap (основные данные)",
    pg_size_pretty(pg_relation_size(c.oid, 'fsm')) AS "FSM",
    pg_size_pretty(pg_relation_size(c.oid, 'vm')) AS "VM",
    pg_size_pretty(pg_relation_size(c.reltoastrelid)) AS "TOAST",
    pg_size_pretty(pg_indexes_size(c.oid)) AS "Индексы"
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE c.relkind IN ('r','m')
    AND n.nspname NOT IN ('pg_catalog','information_schema')
    AND NOT EXISTS (SELECT 1 FROM pg_locks WHERE relation = c.oid AND mode = 'AccessExclusiveLock' AND granted)
    AND pg_total_relation_size(c.oid) > 500*1024
ORDER BY pg_total_relation_size(c.oid) DESC
LIMIT 20;


-- Основные параметры памяти
SELECT
    name AS параметр,
    setting AS значение,
    unit AS единица_измерения,
    CASE name
        WHEN 'gp_vmem_protect_limit' THEN 'Макс. память сегмента (защита от OOM)'
        WHEN 'maintenance_work_mem' THEN 'Память для обслуживающих операций (VACUUM, INDEX)'
        WHEN 'shared_buffers' THEN 'Кэш данных в оперативной памяти'
        WHEN 'statement_mem' THEN 'Лимит памяти на один запрос'
        WHEN 'work_mem' THEN 'Память на одну операцию (сортировка, хэш)'
        ELSE 'Неизвестный параметр'
    END AS описание
FROM pg_settings
WHERE name IN (
    'gp_vmem_protect_limit',
    'maintenance_work_mem',
    'shared_buffers',
    'statement_mem',
    'work_mem'
)
ORDER BY name;


-- Параметры памяти по сегментам
SELECT
    name AS параметр,
    CASE
        WHEN unit = '8kB' THEN ROUND((setting::numeric * 8) / 1024 / 1024, 2)::text || ' GB'
        WHEN unit = 'kB' THEN ROUND(setting::numeric / 1024, 2)::text || ' MB'
        WHEN unit = 'MB' THEN setting::text || ' MB'
        WHEN unit = 'GB' THEN setting::text || ' GB'
        ELSE setting::text || ' ' || COALESCE(unit, '')
    END AS размер_памяти,
    setting AS системное_значение,
    unit AS системная_единица,
    CASE name
        WHEN 'gp_vmem_protect_limit' THEN '⚠️ Защита сегмента от падения (OOM Killer)'
        WHEN 'maintenance_work_mem' THEN '🔧 Для VACUUM, CREATE INDEX, ALTER TABLE'
        WHEN 'shared_buffers' THEN '💾 Кэш "горячих" данных в RAM'
        WHEN 'statement_mem' THEN '🚦 Потолок памяти для одного запроса'
        WHEN 'work_mem' THEN '⚡ На операцию: SORT, HASH JOIN, AGGREGATE'
        ELSE '❓ Другой параметр'
    END AS роль_в_системе
FROM pg_settings
WHERE name IN (
    'gp_vmem_protect_limit',
    'maintenance_work_mem',
    'shared_buffers',
    'statement_mem',
    'work_mem'
)
ORDER BY name;


-- Расчет доступной памяти
SHOW gp_vmem_protect_limit;


--  Конфигурации сколько памяти выделено
SELECT * FROM gp_toolkit.gp_resgroup_config;
SHOW statement_mem;
SHOW max_statement_mem;


-- Сервера
SELECT DISTINCT hostname FROM gp_segment_configuration;


-- Посмотреть настройки групп ресурсов
SELECT version();


-- Самые большие схемы
SELECT
    n.nspname AS schema_name,
    pg_size_pretty(SUM(pg_total_relation_size(c.oid))) AS total_size
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE c.relkind IN ('r', 'm')
  AND n.nspname NOT IN ('pg_catalog', 'information_schema')
GROUP BY n.nspname
ORDER BY SUM(pg_total_relation_size(c.oid)) DESC;


-- Самые большие таблицы с владельцем
SELECT
    n.nspname AS schema_name,
    c.relname AS table_name,
    pg_get_userbyid(c.relowner) AS owner,
    pg_size_pretty(pg_total_relation_size(c.oid)) AS total_size,
    pg_size_pretty(pg_relation_size(c.oid)) AS table_size,
    pg_size_pretty(pg_indexes_size(c.oid)) AS indexes_size
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE c.relkind = 'r'
  AND n.nspname NOT IN ('pg_catalog', 'information_schema')
ORDER BY pg_total_relation_size(c.oid) DESC
LIMIT 50;