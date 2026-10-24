"""Запросы PDF-отчёта: разделы сводки по подключению (используются в views/reports.py)."""

REPORT_MAX_ROWS = 50
USER_SCHEMAS_FILTER_SQL = "namespace.nspname NOT IN ('pg_catalog', 'information_schema') AND namespace.nspname NOT LIKE 'pg_toast%%'"


REPORT_GENERAL_INFO_SQL = """SELECT version(), current_database(), pg_database_size(current_database()), current_setting('server_encoding'), current_setting('TimeZone'), pg_postmaster_start_time(), now() - pg_postmaster_start_time(), (SELECT count(*) FROM pg_stat_activity), current_setting('max_connections')"""


REPORT_SCHEMA_SIZES_SQL = f"""SELECT namespace.nspname, pg_get_userbyid(namespace.nspowner), count(rel.oid), COALESCE(sum(pg_total_relation_size(rel.oid)), 0), pg_size_pretty(COALESCE(sum(pg_total_relation_size(rel.oid)), 0)) FROM pg_namespace namespace LEFT JOIN pg_class rel ON rel.relnamespace=namespace.oid AND rel.relkind IN ('r','p','m') WHERE {USER_SCHEMAS_FILTER_SQL} GROUP BY namespace.nspname, namespace.nspowner ORDER BY 4 DESC LIMIT {REPORT_MAX_ROWS}"""


REPORT_PERFORMANCE_SUMMARY_SQL = """SELECT numbackends, xact_commit, xact_rollback, blks_hit, blks_read, ROUND(100.0 * blks_hit / NULLIF(blks_hit + blks_read, 0), 2), tup_returned, tup_fetched, tup_inserted, tup_updated, tup_deleted, temp_files, temp_bytes, deadlocks, blk_read_time, blk_write_time, stats_reset FROM pg_stat_database WHERE datname=current_database()"""


REPORT_LARGEST_TABLES_SQL = f"""SELECT namespace.nspname, rel.relname, pg_get_userbyid(rel.relowner), pg_total_relation_size(rel.oid), pg_size_pretty(pg_total_relation_size(rel.oid)), pg_indexes_size(rel.oid), pg_size_pretty(pg_indexes_size(rel.oid)), GREATEST(rel.reltuples::bigint,0) FROM pg_class rel JOIN pg_namespace namespace ON namespace.oid=rel.relnamespace WHERE rel.relkind IN ('r','p') AND {USER_SCHEMAS_FILTER_SQL} ORDER BY 4 DESC LIMIT {REPORT_MAX_ROWS}"""


REPORT_TEMP_TABLES_SQL = f"""SELECT namespace.nspname, rel.relname, pg_get_userbyid(rel.relowner), pg_total_relation_size(rel.oid), pg_size_pretty(pg_total_relation_size(rel.oid)) FROM pg_class rel JOIN pg_namespace namespace ON namespace.oid=rel.relnamespace WHERE rel.relkind IN ('r','p') AND (rel.relpersistence='t' OR namespace.nspname LIKE 'pg_temp_%%') ORDER BY 4 DESC LIMIT {REPORT_MAX_ROWS}"""


REPORT_ACTIVE_QUERIES_SQL = f"""SELECT pid, usename, state, now()-query_start, query FROM pg_stat_activity WHERE state='active' AND pid<>pg_backend_pid() ORDER BY query_start LIMIT {REPORT_MAX_ROWS}"""


REPORT_ACTIVE_SESSIONS_SQL = f"""SELECT pid, usename, datname, application_name, COALESCE(client_addr::text,'local'), state, now()-backend_start FROM pg_stat_activity ORDER BY backend_start LIMIT {REPORT_MAX_ROWS}"""


REPORT_LOCKS_SQL = f"""SELECT blocked.pid, blocked.usename, blocker.pid, blocker.usename, now()-blocked.query_start, blocked.query FROM pg_stat_activity blocked CROSS JOIN LATERAL unnest(pg_blocking_pids(blocked.pid)) blocker_pid JOIN pg_stat_activity blocker ON blocker.pid=blocker_pid ORDER BY blocked.query_start LIMIT {REPORT_MAX_ROWS}"""


REPORT_IDLE_TRANSACTIONS_SQL = f"""SELECT pid, usename, application_name, COALESCE(client_addr::text,'local'), state, now()-xact_start, query FROM pg_stat_activity WHERE xact_start IS NOT NULL AND pid<>pg_backend_pid() ORDER BY xact_start LIMIT {REPORT_MAX_ROWS}"""


REPORT_WAIT_EVENTS_SQL = """SELECT COALESCE(wait_event_type, 'CPU / без ожидания'), COALESCE(wait_event, '—'), count(*) FROM pg_stat_activity WHERE datname=current_database() AND pid<>pg_backend_pid() GROUP BY wait_event_type, wait_event ORDER BY 3 DESC"""


REPORT_TABLE_ACCESS_SQL = f"""SELECT schemaname, relname, seq_scan, COALESCE(idx_scan, 0), ROUND(100.0 * COALESCE(idx_scan, 0) / NULLIF(seq_scan + COALESCE(idx_scan, 0), 0), 2), n_live_tup, n_dead_tup, ROUND(100.0 * n_dead_tup / NULLIF(n_live_tup + n_dead_tup, 0), 2), last_autovacuum, last_autoanalyze FROM pg_stat_user_tables ORDER BY n_live_tup DESC LIMIT {REPORT_MAX_ROWS}"""


REPORT_MEMORY_SQL = """SELECT name, setting, unit FROM pg_settings WHERE name IN ('shared_buffers','work_mem','maintenance_work_mem','effective_cache_size','temp_buffers','statement_mem','max_statement_mem','gp_vmem_protect_limit') ORDER BY name"""


REPORT_MAINTENANCE_SQL = f"""SELECT schemaname, relname, n_live_tup, n_dead_tup, last_vacuum, last_autovacuum, last_analyze, last_autoanalyze FROM pg_stat_user_tables ORDER BY n_dead_tup DESC LIMIT {REPORT_MAX_ROWS}"""


REPORT_USERS_SQL = f"""SELECT rolname, rolcanlogin, rolsuper, rolcreatedb, rolcreaterole, rolconnlimit FROM pg_roles WHERE rolcanlogin ORDER BY rolname LIMIT {REPORT_MAX_ROWS}"""


REPORT_GROUPS_SQL = f"""SELECT role.rolname, count(member.oid), COALESCE(string_agg(member.rolname, ', ' ORDER BY member.rolname),'—') FROM pg_roles role LEFT JOIN pg_auth_members membership ON membership.roleid=role.oid LEFT JOIN pg_roles member ON member.oid=membership.member WHERE NOT role.rolcanlogin GROUP BY role.rolname ORDER BY role.rolname LIMIT {REPORT_MAX_ROWS}"""


REPORT_EXPENSIVE_QUERIES_SQL = f"""SELECT calls, ROUND(COALESCE((to_jsonb(statement)->>'total_exec_time')::numeric, (to_jsonb(statement)->>'total_time')::numeric), 2), ROUND(COALESCE((to_jsonb(statement)->>'mean_exec_time')::numeric, (to_jsonb(statement)->>'mean_time')::numeric), 2), rows, query FROM pg_stat_statements statement ORDER BY COALESCE((to_jsonb(statement)->>'total_exec_time')::numeric, (to_jsonb(statement)->>'total_time')::numeric) DESC LIMIT {REPORT_MAX_ROWS}"""


REPORT_GP_SEGMENTS_SQL = "SELECT content, dbid, role, preferred_role, mode, status, hostname, port FROM gp_segment_configuration ORDER BY content, role"


REPORT_PG_STAT_STATEMENTS_CHECK_SQL = "SELECT 1 FROM pg_extension WHERE extname='pg_stat_statements'"
