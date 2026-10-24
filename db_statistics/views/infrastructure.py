from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

from db_statistics.queries import infrastructure_sql
from db_statistics.views.auth import _require_greenplum_connection, _require_payload_connection
from db_statistics.views.helpers import _read_json_body
from db_statistics.views.pool import _fetch_db_resultsets, _open_database_connection, _query_or_error


@require_http_methods(["POST"])
def database_overview(request):
    """Возвращает основные показатели и размеры базы данных."""
    payload = _read_json_body(request)
    db_connection, error_response = _require_payload_connection(request, payload)
    if error_response:
        return error_response
    overview_query = infrastructure_sql.overview_sql()

    extensions_query = infrastructure_sql.EXTENSIONS_SQL

    result, error_response = _query_or_error("Не удалось получить обзор БД", lambda: _fetch_db_resultsets(db_connection, (overview_query, [db_connection.database] * 7), (extensions_query, None)))
    if error_response:
        return error_response
    overview_rows, extension_rows = result
    row = overview_rows[0]

    installed_extensions = [{"name": extension_row[0] or "—", "version": extension_row[1] or "—", "schema": extension_row[2] or "—", "description": extension_row[3] or "—"} for extension_row in extension_rows]

    metrics = [
        {"key": "total", "label": "Общий размер БД", "size_bytes": int(row[4] or 0)},
        {"key": "indexes", "label": "Размер индексов", "size_bytes": int(row[5] or 0)},
        {"key": "data_without_indexes", "label": "Размер БД без индексов", "size_bytes": int(row[6] or 0)},
        {"key": "temp_tables", "label": "Размер временных таблиц", "size_bytes": int(row[7] or 0)},
        {"key": "materialized_views", "label": "Размер материализованных представлений", "size_bytes": int(row[8] or 0)},
    ]
    memory_settings = [
        {"key": "statement_mem", "label": "Память на один запрос", "setting": "statement_mem", "value": row[1] or "—"},
        {"key": "max_statement_mem", "label": "Максимальная память на запрос", "setting": "max_statement_mem", "value": row[2] or "—"},
        {"key": "gp_vmem_protect_limit", "label": "Лимит виртуальной памяти сегмента", "setting": "gp_vmem_protect_limit", "value": row[3] or "—"},
    ]
    connection_info = [{"label": "Хост", "value": db_connection.host}, {"label": "Порт", "value": db_connection.port}]
    role_counts = [{"label": "Пользователи", "count": int(row[9] or 0)}, {"label": "Группы", "count": int(row[10] or 0)}]
    connection_slots = [
        {"key": "current_connections", "label": "Текущие подключения", "value": int(row[11] or 0)},
        {"key": "max_connections", "label": "Максимум подключений", "value": int(row[12] or 0)},
        {"key": "usage_percent", "label": "Использование", "value": float(row[13] or 0)},
    ]
    transaction_total = int(row[25] or 0) + int(row[26] or 0)
    activity_stats = [
        {"key": "xact_commit", "label": "Коммитов", "value": int(row[25] or 0)},
        {"key": "xact_rollback", "label": "Роллбеков", "value": int(row[26] or 0)},
        {"key": "total_transactions", "label": "Всего транзакций", "value": transaction_total},
        {"key": "rollback_percent", "label": "Откат (Rollback), %", "value": f"{float(row[27] or 0):.2f}%"},
        {"key": "cache_hit_percent", "label": "Доля попаданий в кэш", "value": f"{float(row[28] or 0):.2f}%"},
        {"key": "xid_age", "label": "Возраст транзакций (XID)", "value": int(row[29] or 0)},
    ]
    basic_settings = [
        {"key": "host", "label": "Хост", "value": db_connection.host},
        {"key": "port", "label": "Порт", "value": db_connection.port},
        {"key": "server_uptime", "label": "Время работы БД", "value": str(row[15]) if row[15] else "—"},
        {"key": "server_started_at", "label": "Запущена", "value": row[14].strftime("%Y-%m-%d %H:%M:%S") if row[14] else "—"},
        {"key": "server_version", "label": "Версия сервера", "value": row[16] or "—"},
        {"key": "server_encoding", "label": "Кодировка сервера", "value": row[17] or "—"},
        {"key": "timezone", "label": "Часовой пояс", "value": row[18] or "—"},
        {"key": "superuser_reserved_connections", "label": "Резерв подключений суперпользователя", "value": row[19] or "—"},
        {"key": "statement_timeout", "label": "Таймаут запроса", "value": row[20] or "—"},
        {"key": "lock_timeout", "label": "Таймаут ожидания блокировки", "value": row[21] or "—"},
        {"key": "idle_in_transaction_session_timeout", "label": "Таймаут простоя в транзакции", "value": row[22] or "—"},
        {"key": "default_transaction_isolation", "label": "Уровень изоляции по умолчанию", "value": row[23] or "—"},
        {"key": "date_style", "label": "Формат даты", "value": row[24] or "—"},
    ]
    return JsonResponse(
        {
            "ok": True,
            "database": db_connection.database,
            "database_version": row[0] or "—",
            "connection_info": connection_info,
            "metrics": metrics,
            "memory_settings": memory_settings,
            "role_counts": role_counts,
            "connection_slots": connection_slots,
            "activity_stats": activity_stats,
            "basic_settings": basic_settings,
            "installed_extensions": installed_extensions,
        }
    )


@require_http_methods(["POST"])
def segments_info(request):
    """Возвращает состояние и конфигурацию сегментов Greenplum."""
    payload = _read_json_body(request)
    db_connection, error_response = _require_greenplum_connection(request, payload)
    if error_response:
        return error_response
    config_query = infrastructure_sql.CONFIG_SQL
    health_query = infrastructure_sql.HEALTH_SQL
    metrics_query = infrastructure_sql.METRICS_SQL

    def _fetch_segments_data():
        with _open_database_connection(db_connection) as connection:
            with connection.cursor() as cursor:
                cursor.execute(config_query)
                segment_rows = cursor.fetchall()
                cursor.execute(health_query)
                health_row = cursor.fetchone()
                cursor.execute(metrics_query)
                metric_rows = cursor.fetchall()
        return segment_rows, health_row, metric_rows

    result, error_response = _query_or_error("Не удалось получить информацию о сегментах", _fetch_segments_data)
    if error_response:
        return error_response
    segment_rows, health_row, metric_rows = result
    segments = [{"segment": row[0], "role": row[1], "preferred_role": row[2], "mode": row[3], "status": row[4], "port": row[5], "hostname": row[6], "address": row[7]} for row in segment_rows]
    metrics = [{"name": row[0], "value": float(row[1])} for row in metric_rows]

    return JsonResponse({"ok": True, "segments": segments, "health": health_row[1] if health_row else "Нет данных", "metrics": metrics})
