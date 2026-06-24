-- Долгие активные запросы
SELECT
    a.pid,
    a.usename AS "Пользователь",
    n.nspname || '.' || c.relname AS "Объект",
    a.state AS "Состояние",
    now() - a.query_start AS "Длительность",
    a.query AS "SQL"
FROM pg_stat_activity a
JOIN pg_locks l ON l.pid = a.pid AND l.relation IS NOT NULL
JOIN pg_class c ON c.oid = l.relation
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE a.state = 'active'
AND a.usename != 'pustovalov_oyu'
-- AND a.usename = 'dwhnbrb_cube'
ORDER BY (now() - a.query_start) DESC;


-- Транзакционная активность в БД
SELECT
    datname AS "База",
    xact_commit AS "Коммитов",
    xact_rollback AS "Роллбеков",
    xact_commit + xact_rollback AS "Всего транзакций",
    CASE WHEN (xact_commit + xact_rollback) > 0 THEN ROUND(100.0 * xact_rollback / (xact_commit + xact_rollback), 2) ELSE 0 END AS "Откат (Rollback), %"
FROM pg_stat_database
ORDER BY (xact_commit + xact_rollback) DESC;


-- Статистика ожиданий активных клиентских backend’ов
SELECT
    datid AS "OID базы данных",
    datname AS "база данных",
    pid AS "PID серверного процесса",
    sess_id AS "Идентификатор сессии",
    usesysid AS "OID роли (пользователя)",
    usename AS  "Имя пользователя",
    application_name AS "название приложения",
    client_addr AS "IP-адрес клиента",
    client_hostname AS "DNS-имя клиента IP"
FROM pg_stat_activity
WHERE backend_type = 'client backend'
    AND wait_event_type IS NOT NULL
ORDER BY 2 DESC;


-- Список клиентских подключений
SELECT
  pid AS "PID",
  backend_type AS "Тип сеанса",
  client_addr AS "IP клиента",
  application_name AS "Приложение",
  usename AS "Пользователь",
  datname AS "База"
FROM pg_stat_activity
ORDER BY backend_start DESC
LIMIT 200;


-- Отменить запрос
SELECT pg_cancel_backend(2325736);
-- Завершить соединение
SELECT pg_terminate_backend(2325736);
-- Завершить сессию
SELECT pg_terminate_backend(2325736);


-- Отменить запрос
SELECT pg_cancel_backend(pid)
FROM pg_stat_activity
WHERE usename = 'pustovalov_oyu';


-- Удалить все временные таблицы в текущей сессии
SELECT 'DROP TABLE IF EXISTS ' || tablename || ';'
FROM pg_tables
WHERE tablename LIKE 'pg_temp_%'
   OR schemaname = 'pg_temp';


-- Кто кого блокирует
SELECT
    blocked.pid AS blocked_pid,
    blocked.usename AS blocked_user,
    now() - blocked.query_start AS blocked_duration,
    blocked.query AS blocked_query,
    blocker.pid AS blocker_pid,
    blocker.usename AS blocker_user,
    now() - blocker.query_start AS blocker_duration,
    blocker.query AS blocker_query
FROM pg_locks blocked_locks
JOIN pg_stat_activity blocked
    ON blocked.pid = blocked_locks.pid
JOIN pg_locks blocker_locks
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
JOIN pg_stat_activity blocker
    ON blocker.pid = blocker_locks.pid
WHERE NOT blocked_locks.granted
  AND blocker_locks.granted;


-- Сессии idle in transaction
SELECT
    pid,
    usename,
    application_name,
    client_addr,
    state,
    now() - xact_start AS transaction_duration,
    now() - state_change AS idle_duration,
    query
FROM pg_stat_activity
WHERE state = 'idle in transaction'
ORDER BY xact_start;


-- Долгие транзакции
SELECT
    pid,
    usename,
    application_name,
    state,
    xact_start,
    now() - xact_start AS xact_duration,
    query
FROM pg_stat_activity
WHERE xact_start IS NOT NULL
ORDER BY xact_duration DESC;


-- Использование слотов подключений
SELECT
    COUNT(*) AS current_connections,
    setting::int AS max_connections,
    ROUND(COUNT(*) * 100.0 / setting::int, 2) AS usage_percent
FROM pg_stat_activity,
     pg_settings
WHERE name = 'max_connections'
GROUP BY setting;








-- Проверка rollback rate
SELECT
    datname,
    xact_commit,
    xact_rollback,
    xact_commit + xact_rollback AS total_xacts,
    ROUND(
        xact_rollback::numeric /
        NULLIF(xact_commit + xact_rollback, 0) * 100,
        2
    ) AS rollback_percent
FROM pg_stat_database
ORDER BY rollback_percent DESC;


-- Cache hit ratio
SELECT
    datname,
    blks_read,
    blks_hit,
    ROUND(
        blks_hit::numeric / NULLIF(blks_hit + blks_read, 0) * 100,
        2
    ) AS cache_hit_percent
FROM pg_stat_database
ORDER BY cache_hit_percent ASC;


