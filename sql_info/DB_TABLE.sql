-- Постоянные таблицы (исключаем системные схемы)
SELECT
    n.nspname AS "Схема",
    c.relname AS "Таблица",
    obj_description(c.oid) AS "Описание таблицы",
    pg_size_pretty(pg_total_relation_size(c.oid)) AS "Размер таблицы",
    a.attname AS "Столбец",
    pg_catalog.col_description(a.attrelid, a.attnum) AS "Описание столбца",
    t.typname AS "Тип данных"
FROM pg_catalog.pg_attribute a
JOIN pg_catalog.pg_class c ON a.attrelid = c.oid
JOIN pg_catalog.pg_namespace n ON c.relnamespace = n.oid
JOIN pg_catalog.pg_type t ON t.oid = a.atttypid
WHERE a.attnum > 0
    AND NOT a.attisdropped
    AND c.relkind = 'r'
    AND c.relpersistence = 'p'
    AND n.nspname NOT IN ('pg_catalog','information_schema')
ORDER BY n.nspname, c.relname, a.attnum;


-- Количество записей в таблицах
SELECT
    n.nspname AS "Схема",
    a.relname AS "Таблица",
    obj_description(c.oid) AS "Название таблицы",
    a.n_live_tup AS "Количество записей",
    pg_size_pretty(pg_total_relation_size(c.oid)) AS "Размер таблицы",
    pg_get_userbyid(c.relowner) AS "Владелец"
FROM pg_stat_user_tables AS a
JOIN pg_class AS c ON a.relid = c.oid
JOIN pg_namespace AS n ON c.relnamespace = n.oid
ORDER BY a.n_live_tup DESC, a.n_live_tup DESC;


-- Временные таблицы
SELECT
    n.nspname AS "Схема",
    c.relname AS "Таблица",
    obj_description(c.oid) AS "Описание таблицы",
    pg_size_pretty(pg_total_relation_size(c.oid)) AS "Размер таблицы",
    a.attname AS "Столбец",
    pg_catalog.col_description(a.attrelid, a.attnum) AS "Описание столбца",
    t.typname AS "Тип данных"
FROM pg_catalog.pg_attribute a
JOIN pg_catalog.pg_class c ON a.attrelid = c.oid
JOIN pg_catalog.pg_namespace n ON c.relnamespace = n.oid
JOIN pg_catalog.pg_type t ON t.oid = a.atttypid
WHERE a.attnum > 0
    AND NOT a.attisdropped
    AND c.relkind = 'r'
    AND c.relpersistence = 't'
ORDER BY n.nspname, c.relname, a.attnum;


-- Найти сессии с временными таблицами
SELECT
    a.pid,
    a.usename AS "Пользователь",
    a.application_name AS "Приложение",
    a.client_addr AS "IP клиента",
    a.backend_start AS "Начало сессии",
    a.state,
    pg_size_pretty(COALESCE(SUM(pg_total_relation_size(c.oid)), 0)) AS "Размер временных таблиц"
FROM
    pg_stat_activity a
LEFT JOIN
    pg_class c ON c.relowner = a.usesysid
    AND c.relpersistence = 't'
    AND c.relkind = 'r'
LEFT JOIN
    pg_namespace n ON c.relnamespace = n.oid
    AND n.nspname LIKE 'pg_temp%'
GROUP BY
    a.pid, a.usename, a.application_name, a.client_addr, a.backend_start, a.state
ORDER BY
    SUM(pg_total_relation_size(c.oid)) DESC NULLS LAST;


-- Получение скрипта для удаления времееных таблиц
SELECT
    'DROP TABLE IF EXISTS ' || quote_ident(n.nspname) || '.' || quote_ident(c.relname) || ' CASCADE;' AS drop_sql,
    r.rolname AS author
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
JOIN pg_roles r ON r.oid = c.relowner
WHERE c.relkind = 'r' AND c.relpersistence = 't';


-- Таблицы с большим количеством dead rows
SELECT
    schemaname,
    relname AS table_name,
    n_live_tup,
    n_dead_tup,
    ROUND(
        n_dead_tup::numeric / NULLIF(n_live_tup + n_dead_tup, 0) * 100,
        2
    ) AS dead_percent,
    last_vacuum,
    last_autovacuum,
    last_analyze,
    last_autoanalyze
FROM pg_stat_user_tables
ORDER BY dead_percent DESC NULLS LAST
LIMIT 50;


-- Таблицы, по которым давно не было ANALYZE
SELECT
    schemaname,
    relname AS table_name,
    n_live_tup,
    last_analyze,
    last_autoanalyze
FROM pg_stat_user_tables
WHERE last_analyze IS NULL
   OR last_autoanalyze IS NULL
ORDER BY n_live_tup DESC
LIMIT 50;


-- Таблицы без статистики Greenplum
SELECT *
FROM gp_toolkit.gp_stats_missing;


-- Перекос данных по конкретной таблице
SELECT
    gp_segment_id,
    COUNT(*) AS row_count
FROM dc00_sys.dc00006_1725_coderules
GROUP BY gp_segment_id
ORDER BY gp_segment_id;


-- Коэффициент перекоса по всем таблицам
SELECT *
FROM gp_toolkit.gp_skew_coefficients
ORDER BY skccoeff DESC
LIMIT 50;


-- Политика распределения таблиц
SELECT
    n.nspname AS schema_name,
    c.relname AS table_name,
    pg_get_table_distributedby(c.oid) AS distributed_by
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE c.relkind = 'r'
  AND n.nspname NOT IN ('pg_catalog', 'information_schema')
ORDER BY n.nspname, c.relname;


-- Распределение размеров в БД по таблицам
SELECT
    n.nspname AS schema_name,
    c.relname AS table_name,
    pg_size_pretty(pg_relation_size(c.oid)) AS table_size,
    pg_size_pretty(pg_indexes_size(c.oid)) AS indexes_size,
    pg_size_pretty(pg_total_relation_size(c.oid) - pg_relation_size(c.oid) - pg_indexes_size(c.oid)) AS toast_size,  -- механизм PostgreSQL/Greenplum для хранения больших значений вне основной таблицы.
    pg_size_pretty(pg_total_relation_size(c.oid)) AS total_size,
    pg_total_relation_size(c.oid) AS total_size_bytes
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE c.relkind IN ('r', 'm', 'p')
  AND n.nspname NOT IN ('pg_catalog', 'information_schema')
  AND n.nspname NOT LIKE 'pg_toast%'
ORDER BY pg_total_relation_size(c.oid) DESC;


-- Как посмотреть реальную TOAST-таблицу
SELECT
    c.relname AS table_name,
    t.relname AS toast_table
FROM pg_class c
LEFT JOIN pg_class t
    ON t.oid = c.reltoastrelid
WHERE c.relname = 'dc09401_calcvalues';


-- Таблицы + индексы + TOAST отдельно
SELECT
    bdirelid,
    bdinspname AS schema_name,
    bdirelname AS table_name,
    bdirelpages,
    bdiexppages,
    CASE bdidiag
        WHEN 'no bloat detected' THEN 'Раздувание не обнаружено'
        WHEN 'moderate amount of bloat suspected' THEN 'Обнаружено умеренное раздувание'
        WHEN 'significant amount of bloat suspected' THEN 'Обнаружено значительное раздувание'
        ELSE bdidiag
    END AS diagnosis
FROM gp_toolkit.gp_bloat_diag;


-- Раздутие таблицы
SELECT
    bdinspname AS "Схема",
    bdirelname AS "Таблица",
    bdirelpages AS "Фактические страницы",
    bdiexppages AS "Ожидаемые_страницы",
    ROUND((bdirelpages - bdiexppages)::numeric / NULLIF(bdiexppages, 0) * 100, 2) AS "Процент вздутия",
    bdidiag AS "Информация"
FROM gp_toolkit.gp_bloat_diag;


-- Статистика обслуживания пользовательских таблиц
SELECT
    schemaname,
    relname AS table_name,
    last_vacuum,
    last_autovacuum,
    last_analyze,
    last_autoanalyze,
    n_live_tup,
    n_dead_tup
FROM pg_stat_user_tables
ORDER BY n_dead_tup DESC
LIMIT 50;