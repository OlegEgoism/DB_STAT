from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from db_statistics.queries import performance_sql
from db_statistics.views.auth import _require_payload_connection
from db_statistics.views.formatting import _duration_seconds, _format_duration
from db_statistics.views.helpers import _read_json_body
from db_statistics.views.maintenance import _terminate_backend
from db_statistics.views.pagination import _like_search_pattern
from db_statistics.views.pool import _fetch_db_rows, _query_or_error


@require_http_methods(["POST"])
def active_queries(request):
    """Возвращает активные запросы выбранного подключения."""
    payload = _read_json_body(request)
    db_connection, error_response = _require_payload_connection(request, payload)
    if error_response:
        return error_response
    username = (payload.get("username") or "").strip()
    username_pattern = _like_search_pattern(username) if username else ""
    active_queries_query = performance_sql.ACTIVE_QUERIES_SQL

    rows, error_response = _query_or_error("Не удалось получить активные запросы", lambda: _fetch_db_rows(db_connection, active_queries_query, [username, username_pattern]))
    if error_response:
        return error_response

    queries = []
    for row in rows:
        duration = row[4]
        queries.append({"pid": row[0], "username": row[1] or "—", "relation_name": row[2] or "—", "state": row[3] or "—", "duration": _format_duration(duration), "duration_seconds": _duration_seconds(duration), "sql": row[5] or "—"})
    return JsonResponse({"ok": True, "queries": queries, "total_count": len(queries), "username": username})


@require_http_methods(["POST"])
def terminate_active_query(request):
    """Завершает активный запрос по идентификатору процесса."""
    return _terminate_backend(
        request,
        require_active=True,
        invalid_pid_message="Указан некорректный PID запроса",
        not_found_message=lambda pid: f"Активный запрос с PID {pid} не найден",
        failed_message=lambda pid: f"Не удалось завершить запрос с PID {pid}",
        success_message=lambda pid: f"Запрос с PID {pid} завершён",
        audit_action_type="query_terminate",
        audit_label="Завершение активного запроса",
    )


@require_http_methods(["POST"])
def active_sessions(request):
    """Возвращает активные пользовательские сессии базы данных."""
    payload = _read_json_body(request)
    db_connection, error_response = _require_payload_connection(request, payload)
    if error_response:
        return error_response
    username = (payload.get("username") or "").strip()
    username_pattern = _like_search_pattern(username) if username else ""
    state = (payload.get("state") or "").strip()
    sessions_query = performance_sql.SESSIONS_SQL

    rows, error_response = _query_or_error("Не удалось получить активные сессии и подключения", lambda: _fetch_db_rows(db_connection, sessions_query, [username, username_pattern, state, state]))
    if error_response:
        return error_response

    sessions = []
    state_counts = {}
    user_counts = {}
    client_counts = {}
    for row in rows:
        session_duration = row[14]
        query_duration = row[15]
        row_state = row[10] or "—"
        row_user = row[1] or "—"
        row_client = str(row[4]) if row[4] else "local"
        state_counts[row_state] = state_counts.get(row_state, 0) + 1
        user_counts[row_user] = user_counts.get(row_user, 0) + 1
        client_counts[row_client] = client_counts.get(row_client, 0) + 1
        sessions.append(
            {
                "pid": row[0],
                "username": row_user,
                "database": row[2] or "—",
                "application_name": row[3] or "—",
                "client_addr": row_client,
                "client_port": row[5] if row[5] is not None else "—",
                "backend_start": (timezone.localtime(row[6]).strftime("%Y-%m-%d %H:%M:%S") if row[6] else "—"),
                "state": row_state,
                "wait_event": " / ".join([part for part in [row[11], row[12]] if part]) or "—",
                "backend_type": row[13] or "—",
                "session_duration": _format_duration(session_duration),
                "session_duration_seconds": _duration_seconds(session_duration),
                "query_duration": _format_duration(query_duration),
                "query_duration_seconds": _duration_seconds(query_duration),
                "sql": row[16] or "—",
            }
        )

    summary = {
        "total": len(sessions),
        "active": state_counts.get("active", 0),
        "idle": state_counts.get("idle", 0),
        "idle_in_transaction": state_counts.get("idle in transaction", 0),
        "users": len(user_counts),
        "clients": len(client_counts),
        "states": [{"state": key, "count": value} for key, value in sorted(state_counts.items())],
    }
    return JsonResponse({"ok": True, "sessions": sessions, "summary": summary, "total_count": len(sessions), "username": username, "state": state})


@require_http_methods(["POST"])
def terminate_active_session(request):
    """Завершает пользовательскую сессию базы данных."""
    return _terminate_backend(
        request,
        require_active=False,
        invalid_pid_message="Указан некорректный PID сессии",
        not_found_message=lambda pid: f"Сессия с PID {pid} не найдена",
        failed_message=lambda pid: f"Не удалось завершить сессию с PID {pid}",
        success_message=lambda pid: f"Сессия с PID {pid} завершена",
        audit_action_type="session_terminate",
        audit_label="Завершение активной сессии",
    )


@require_http_methods(["POST"])
def terminate_lock_process(request):
    """Завершает заблокированный или блокирующий процесс."""
    return _terminate_backend(
        request,
        require_active=False,
        invalid_pid_message="Указан некорректный PID процесса блокировки",
        not_found_message=lambda pid: f"Процесс блокировки с PID {pid} не найден",
        failed_message=lambda pid: f"Не удалось завершить процесс блокировки с PID {pid}",
        success_message=lambda pid: f"Процесс блокировки с PID {pid} завершён",
        audit_action_type="lock_terminate",
        audit_label="Завершение процесса блокировки",
    )


@require_http_methods(["POST"])
def terminate_idle_transaction(request):
    """Завершает процесс с простаивающей транзакцией."""
    return _terminate_backend(
        request,
        require_active=False,
        invalid_pid_message="Указан некорректный PID транзакции",
        not_found_message=lambda pid: f"Транзакция с PID {pid} не найдена",
        failed_message=lambda pid: f"Не удалось завершить транзакцию с PID {pid}",
        success_message=lambda pid: f"Транзакция с PID {pid} завершена",
        audit_action_type="transaction_terminate",
        audit_label="Завершение простаивающей транзакции",
    )


@require_http_methods(["POST"])
def blocking_locks(request):
    """Возвращает цепочки блокирующих и заблокированных процессов."""
    payload = _read_json_body(request)
    db_connection, error_response = _require_payload_connection(request, payload)
    if error_response:
        return error_response
    blocked_username = (payload.get("blocked_username") or "").strip()
    blocker_username = (payload.get("blocker_username") or "").strip()
    blocked_username_pattern = _like_search_pattern(blocked_username) if blocked_username else ""
    blocker_username_pattern = _like_search_pattern(blocker_username) if blocker_username else ""
    blocking_locks_query = performance_sql.BLOCKING_LOCKS_SQL

    rows, error_response = _query_or_error("Не удалось получить блокировки", lambda: _fetch_db_rows(db_connection, blocking_locks_query, [blocked_username, blocked_username_pattern, blocker_username, blocker_username_pattern]))
    if error_response:
        return error_response

    locks = []
    for row in rows:
        blocked_duration = row[2]
        blocker_duration = row[6]
        locks.append(
            {
                "blocked_pid": row[0],
                "blocked_user": row[1] or "—",
                "blocked_duration": _format_duration(blocked_duration),
                "blocked_query": row[3] or "—",
                "blocker_pid": row[4],
                "blocker_user": row[5] or "—",
                "blocker_duration": _format_duration(blocker_duration),
                "blocker_query": row[7] or "—",
            }
        )
    return JsonResponse({"ok": True, "locks": locks, "total_count": len(locks), "blocked_username": blocked_username, "blocker_username": blocker_username})


@require_http_methods(["POST"])
def idle_transactions(request):
    """Возвращает простаивающие транзакции выбранного подключения."""
    payload = _read_json_body(request)
    db_connection, error_response = _require_payload_connection(request, payload)
    if error_response:
        return error_response
    username = (payload.get("username") or "").strip()
    username_pattern = _like_search_pattern(username) if username else ""
    idle_transactions_query = performance_sql.IDLE_TRANSACTIONS_SQL

    rows, error_response = _query_or_error("Не удалось получить транзакции", lambda: _fetch_db_rows(db_connection, idle_transactions_query, [username, username_pattern]))
    if error_response:
        return error_response

    transactions = []
    for row in rows:
        transaction_duration = row[5]
        idle_duration = row[6]
        transactions.append(
            {
                "pid": row[0],
                "username": row[1] or "—",
                "application_name": row[2] or "—",
                "client_addr": str(row[3]) if row[3] else "—",
                "state": row[4] or "—",
                "transaction_duration": _format_duration(transaction_duration),
                "idle_duration": _format_duration(idle_duration),
                "sql": row[7] or "—",
            }
        )
    return JsonResponse({"ok": True, "transactions": transactions, "total_count": len(transactions), "username": username})
