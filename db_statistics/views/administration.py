from django.conf import settings
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

from db_statistics.models import MaintenanceJob, ReportJob
from db_statistics.queries import administration_sql
from db_statistics.views.audit import _maintenance_operation_audit_info, _write_audit
from db_statistics.views.auth import _current_db_user, _destructive_action_permission_error, _rate_limit_exceeded, _rate_limit_response, _require_payload_connection
from db_statistics.views.helpers import _format_bytes, _parse_pg_size_to_bytes, _read_json_body
from db_statistics.views.maintenance import _serialize_maintenance_job, _submit_maintenance_job
from db_statistics.views.pagination import _escape_like_pattern, _favorite_filter, _list_query_params, _multi_column_search_filter
from db_statistics.views.pool import _fetch_db_row, _fetch_db_rows, _query_or_error
from db_statistics.views.reports import _ensure_report_job_table, _serialize_report_job


@require_http_methods(["POST"])
def memory_overview(request):
    """Возвращает параметры и показатели использования памяти базы данных."""
    payload = _read_json_body(request)
    db_connection, error_response = _require_payload_connection(request, payload)
    if error_response:
        return error_response
    memory_query = administration_sql.memory_sql()

    row, error_response = _query_or_error("Не удалось получить параметры памяти", lambda: _fetch_db_row(db_connection, memory_query, [db_connection.database, db_connection.database]))
    if error_response:
        return error_response

    settings = [
        {"key": "gp_vmem_protect_limit", "label": "Лимит виртуальной памяти сегмента", "value": row[0] or "—", "role": "Защита OOM"},
        {"key": "shared_buffers", "label": "Кэш данных", "value": row[1] or "—", "role": "Буферы"},
        {"key": "work_mem", "label": "Память операций", "value": row[2] or "—", "role": "Сортировка/Hash"},
        {"key": "maintenance_work_mem", "label": "Память обслуживания", "value": row[3] or "—", "role": "Очистка / создание индекса"},
        {"key": "statement_mem", "label": "Память запроса", "value": row[4] or "—", "role": "Лимит запроса"},
        {"key": "max_statement_mem", "label": "Максимальная память запроса", "value": row[5] or "—", "role": "Макс. лимит"},
    ]

    sizes = {
        # Greenplum отображает параметр gp_vmem_protect_limit как число в МБ, в отличие от других параметров, значения которых обычно содержат единицу измерения.
        "gp_vmem_protect_limit": _parse_pg_size_to_bytes(row[0], default_unit="MB"),
        "shared_buffers": _parse_pg_size_to_bytes(row[1]),
        "work_mem": _parse_pg_size_to_bytes(row[2]),
        "maintenance_work_mem": _parse_pg_size_to_bytes(row[3]),
        "statement_mem": _parse_pg_size_to_bytes(row[4]),
        "max_statement_mem": _parse_pg_size_to_bytes(row[5]),
    }

    def usage_row(label, used_key, limit_key):
        """Формирует строку показателя использования памяти."""
        used = sizes.get(used_key)
        limit = sizes.get(limit_key)
        percent = round((used * 100 / limit), 2) if used is not None and limit else 0
        return {"label": label, "used": _format_bytes(used), "limit": _format_bytes(limit), "usage_percent": percent}

    usage = [
        usage_row("Память запроса", "statement_mem", "max_statement_mem"),
        usage_row("Максимальная память запроса", "max_statement_mem", "gp_vmem_protect_limit"),
        usage_row("Память операций", "work_mem", "max_statement_mem"),
        usage_row("Кэш данных", "shared_buffers", "gp_vmem_protect_limit"),
    ]
    size_metrics = [
        {"key": "total", "label": "Общий размер БД", "size_bytes": int(row[6] or 0), "value": _format_bytes(int(row[6] or 0))},
        {"key": "indexes", "label": "Размер индексов", "size_bytes": int(row[7] or 0), "value": _format_bytes(int(row[7] or 0))},
        {"key": "data_without_indexes", "label": "Размер БД без индексов", "size_bytes": int(row[8] or 0), "value": _format_bytes(int(row[8] or 0))},
        {"key": "temp_tables", "label": "Размер временных таблиц", "size_bytes": int(row[9] or 0), "value": _format_bytes(int(row[9] or 0))},
        {"key": "materialized_views", "label": "Размер материализованных представлений", "size_bytes": int(row[10] or 0), "value": _format_bytes(int(row[10] or 0))},
    ]
    return JsonResponse({"ok": True, "settings": settings, "usage": usage, "size_metrics": size_metrics})


@require_http_methods(["POST"])
def database_users_list(request):
    """Возвращает список пользователей выбранной базы данных."""
    return _database_roles_list(request, can_login=True)


@require_http_methods(["POST"])
def database_groups_list(request):
    """Возвращает список групп выбранной базы данных."""
    return _database_roles_list(request, can_login=False)


@require_http_methods(["POST"])
def maintenance_stats(request):
    """Возвращает статистику обслуживания таблиц базы данных."""
    payload = _read_json_body(request)
    db_connection, error_response = _require_payload_connection(request, payload)
    if error_response:
        return error_response
    page, page_size, offset, search, sort_column, direction = _list_query_params(
        payload, {"schema_name": "schemaname", "table_name": "relname", "live_rows": "live_rows", "dead_rows": "dead_rows", "dead_percent": "dead_percent", "last_vacuum": "last_vacuum_at", "last_analyze": "last_analyze_at"}, "dead_rows"
    )
    where_sql = ""
    params = []
    if search:
        search_pattern = f"%{_escape_like_pattern(search)}%"
        where_sql = "WHERE schemaname ILIKE %s ESCAPE '!' OR relname ILIKE %s ESCAPE '!'"
        params.extend([search_pattern, search_pattern])

    maintenance_query = administration_sql.maintenance_sql(direction=direction, sort_column=sort_column, where_sql=where_sql)

    rows, error_response = _query_or_error("Не удалось получить статистику обслуживания", lambda: _fetch_db_rows(db_connection, maintenance_query, [*params, page_size, offset]))
    if error_response:
        return error_response

    def format_datetime(value):
        """Форматирует дату и время статистики обслуживания."""
        return value.strftime("%Y-%m-%d %H:%M:%S") if value else "Никогда"

    tables = [{"schema_name": row[0], "table_name": row[1], "live_rows": int(row[2] or 0), "dead_rows": int(row[3] or 0), "dead_percent": float(row[4] or 0), "last_vacuum": format_datetime(row[5]), "last_analyze": format_datetime(row[6])} for row in rows]
    total_count = int(rows[0][7]) if rows else 0
    return JsonResponse({"ok": True, "tables": tables, "page": page, "page_size": page_size, "total_count": total_count})


@require_http_methods(["POST"])
def maintenance_operation(request):
    """Запускает фоновое обслуживание или возвращает состояние задачи."""
    permission_error = _destructive_action_permission_error(request)
    if permission_error:
        return permission_error
    db_user = _current_db_user(request)

    payload = _read_json_body(request)
    if payload.get("job_id"):
        try:
            job = MaintenanceJob.objects.select_related("connection", "user").filter(pk=payload["job_id"], user=db_user).first()
        except (ValueError, ValidationError):
            # job_id is a UUIDField — a malformed value raises here instead of
            # just not matching, which would otherwise surface as a 500.
            job = None
        if not job:
            return JsonResponse({"ok": False, "message": "Задача обслуживания не найдена"}, status=404)
        return JsonResponse({"ok": True, "job": _serialize_maintenance_job(job)})

    # Only rate-limits starting a new operation, not the job_id status poll above.
    if _rate_limit_exceeded(f"rl:maintenance_operation:{db_user.pk}", settings.RATE_LIMIT_MAINTENANCE_OPERATION_MAX, settings.RATE_LIMIT_MAINTENANCE_OPERATION_WINDOW_SECONDS):
        return _rate_limit_response("запуск обслуживания")

    db_connection, error_response = _require_payload_connection(request, payload)
    if error_response:
        return error_response
    schema_name = str(payload.get("schema_name") or "").strip()
    table_name = str(payload.get("table_name") or "").strip()
    operation = str(payload.get("operation") or "vacuum").lower()
    if not schema_name or not table_name:
        return JsonResponse({"ok": False, "message": "Не выбрана таблица для обслуживания"}, status=400)
    if operation not in {"vacuum", "vacuum_full", "analyze", "explain_analyze"}:
        return JsonResponse({"ok": False, "message": "Неизвестная операция обслуживания"}, status=400)

    job = MaintenanceJob.objects.create(user=db_user, connection=db_connection, operation=operation, schema_name=schema_name, table_name=table_name)
    _write_audit(operation, _maintenance_operation_audit_info(operation, db_connection, schema_name, table_name, "запущено в фоновом режиме"), db_user=db_user)
    _submit_maintenance_job(job.pk)
    return JsonResponse({"ok": True, "job": _serialize_maintenance_job(job)}, status=202)


@require_http_methods(["GET", "POST"])
def maintenance_jobs(request):
    """Возвращает сохранённую историю фоновых задач текущего пользователя."""
    db_user = _current_db_user(request)
    if not db_user:
        return JsonResponse({"ok": False, "message": "Требуется вход в приложение"}, status=401)
    _ensure_report_job_table()
    maintenance_jobs = [_serialize_maintenance_job(job) for job in MaintenanceJob.objects.select_related("connection", "user").filter(user=db_user)[:25]]
    report_jobs = [_serialize_report_job(job) for job in ReportJob.objects.select_related("connection", "user").filter(user=db_user)[:25]]
    jobs = sorted([*maintenance_jobs, *report_jobs], key=lambda job: job["created"], reverse=True)[:25]
    return JsonResponse({"ok": True, "jobs": jobs})


def _format_role_timestamp(value):
    """Форматирует срок действия роли базы данных."""
    if value is None:
        return "Бессрочно"
    return value.strftime("%Y-%m-%d %H:%M:%S") if hasattr(value, "strftime") else str(value)


def _role_flag(value):
    """Преобразует логический признак роли в отображаемое значение."""
    return "Да" if value else "Нет"


def _database_roles_list(request, *, can_login):
    """Возвращает отфильтрованный список пользователей или групп базы данных."""
    payload = _read_json_body(request)
    db_connection, error_response = _require_payload_connection(request, payload)
    if error_response:
        return error_response
    page, page_size, offset, search, sort_column, direction = _list_query_params(
        payload,
        {"name": "name", "superuser": "superuser", "createdb": "createdb", "createrole": "createrole", "inherit": "inherit", "replication": "replication", "connection_limit": "connection_limit", "valid_until": "valid_until", "member_count": "member_count"},
        "name",
        default_page_size=settings.PAGINATION_DEFAULT_PAGE_SIZE,
    )
    role_type_message = "пользователей" if can_login else "групп"

    where_sql = ""
    params = [can_login]
    if search:
        search_sql, search_params = _multi_column_search_filter(search, ("role_info.rolname",))
        where_sql = search_sql
        params.extend(search_params)
    favorite_sql, favorite_params = _favorite_filter(payload, _current_db_user(request), db_connection, "user" if can_login else "group", ("role_info.rolname",))
    where_sql += f" {favorite_sql}"
    params.extend(favorite_params)

    roles_query = administration_sql.roles_sql(direction=direction, sort_column=sort_column, where_sql=where_sql)

    rows, error_response = _query_or_error(f"Не удалось получить список {role_type_message}", lambda: _fetch_db_rows(db_connection, roles_query, [*params, page_size, offset]))
    if error_response:
        return error_response

    roles = [
        {
            "name": row[0],
            "superuser": _role_flag(row[1]),
            "createdb": _role_flag(row[2]),
            "createrole": _role_flag(row[3]),
            "inherit": _role_flag(row[4]),
            "replication": _role_flag(row[5]),
            "connection_limit": "Без лимита" if row[6] == -1 else str(row[6]),
            "valid_until": _format_role_timestamp(row[7]),
            "member_count": int(row[8] or 0),
        }
        for row in rows
    ]
    total_count = int(rows[0][9]) if rows else 0
    summary = {"total_count": total_count, "superuser_count": int(rows[0][10]) if rows else 0, "createdb_count": int(rows[0][11]) if rows else 0, "replication_count": int(rows[0][12]) if rows else 0, "privileged_count": int(rows[0][13]) if rows else 0}
    return JsonResponse({"ok": True, "roles": roles, "page": page, "page_size": page_size, "total_count": total_count, "summary": summary})
