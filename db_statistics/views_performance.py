from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from db_statistics.view_helpers import _backend_termination_audit_info, _current_db_user, _destructive_action_permission_error, _escape_like_pattern, _fetch_db_row, _fetch_db_rows, _read_json_body, _require_payload_connection, _write_audit


@require_http_methods(["POST"])
def active_queries(request):
    """Возвращает активные запросы выбранного подключения."""
    payload = _read_json_body(request)
    db_connection, error_response = _require_payload_connection(request, payload)
    if error_response:
        return error_response
    username = (payload.get("username") or "").strip()
    username_pattern = f"%{_escape_like_pattern(username)}%" if username else ""
    active_queries_query = """
        WITH locked_relations AS (
            SELECT
                locks.pid,
                string_agg(
                    DISTINCT namespace.nspname || '.' || relation.relname,
                    ', ' ORDER BY namespace.nspname || '.' || relation.relname
                ) AS relation_name
            FROM pg_catalog.pg_locks AS locks
            JOIN pg_catalog.pg_class AS relation
                ON relation.oid = locks.relation
            JOIN pg_catalog.pg_namespace AS namespace
                ON namespace.oid = relation.relnamespace
            WHERE locks.relation IS NOT NULL
            GROUP BY locks.pid
        )
        SELECT
            activity.pid,
            activity.usename,
            COALESCE(locked_relations.relation_name, '—') AS relation_name,
            activity.state,
            GREATEST(now() - activity.query_start, INTERVAL '0 seconds') AS duration,
            activity.query
        FROM pg_catalog.pg_stat_activity AS activity
        LEFT JOIN locked_relations
            ON locked_relations.pid = activity.pid
        WHERE activity.state = 'active'
          AND activity.pid <> pg_backend_pid()
          AND (%s = '' OR activity.usename ILIKE %s ESCAPE '!')
        ORDER BY duration DESC;
    """

    try:
        rows = _fetch_db_rows(
            db_connection, active_queries_query, [username, username_pattern]
        )
    except Exception as exc:
        return JsonResponse(
            {"ok": False, "message": f"Не удалось получить активные запросы: {exc}"},
            status=400,
        )

    queries = []
    for row in rows:
        duration = row[4]
        queries.append(
            {
                "pid": row[0],
                "username": row[1] or "—",
                "relation_name": row[2] or "—",
                "state": row[3] or "—",
                "duration": str(duration).split(".")[0] if duration else "—",
                "duration_seconds": (
                    max(int(duration.total_seconds()), 0) if duration else 0
                ),
                "sql": row[5] or "—",
            }
        )
    return JsonResponse(
        {
            "ok": True,
            "queries": queries,
            "total_count": len(queries),
            "username": username,
        }
    )


@require_http_methods(["POST"])
def terminate_active_query(request):
    """Завершает активный запрос по идентификатору процесса."""
    permission_error = _destructive_action_permission_error(request)
    if permission_error:
        return permission_error
    payload = _read_json_body(request)
    db_connection, error_response = _require_payload_connection(request, payload)
    if error_response:
        return error_response

    try:
        pid = int(payload.get("pid"))
        if pid <= 0:
            raise ValueError
    except (TypeError, ValueError):
        return JsonResponse(
            {"ok": False, "message": "Указан некорректный PID запроса"}, status=400
        )

    terminate_query = """
        SELECT
            pg_catalog.pg_terminate_backend(activity.pid),
            activity.pid,
            activity.usename,
            activity.datname,
            activity.application_name,
            activity.client_addr,
            activity.client_port,
            activity.state,
            activity.backend_type,
            activity.backend_start,
            activity.xact_start,
            activity.query_start,
            activity.state_change,
            activity.wait_event_type,
            activity.wait_event,
            now() - activity.backend_start AS session_duration,
            CASE WHEN activity.query_start IS NULL THEN NULL ELSE now() - activity.query_start END AS query_duration,
            activity.query
        FROM pg_catalog.pg_stat_activity AS activity
        WHERE activity.pid = %s
          AND activity.state = 'active'
          AND activity.pid <> pg_backend_pid();
    """
    try:
        row = _fetch_db_row(db_connection, terminate_query, [pid])
    except Exception as exc:
        return JsonResponse(
            {"ok": False, "message": f"Не удалось завершить запрос с PID {pid}: {exc}"},
            status=400,
        )

    if not row:
        return JsonResponse(
            {"ok": False, "message": f"Активный запрос с PID {pid} не найден"},
            status=404,
        )
    if not row[0]:
        return JsonResponse(
            {"ok": False, "message": f"Не удалось завершить запрос с PID {pid}"},
            status=409,
        )

    _write_audit(
        "query_terminate",
        _backend_termination_audit_info(
            "Завершение активного запроса", db_connection, row
        ),
        db_user=_current_db_user(request),
    )
    return JsonResponse(
        {"ok": True, "message": f"Запрос с PID {pid} завершён", "pid": pid}
    )


@require_http_methods(["POST"])
def active_sessions(request):
    """Возвращает активные пользовательские сессии базы данных."""
    payload = _read_json_body(request)
    db_connection, error_response = _require_payload_connection(request, payload)
    if error_response:
        return error_response
    username = (payload.get("username") or "").strip()
    username_pattern = f"%{_escape_like_pattern(username)}%" if username else ""
    state = (payload.get("state") or "").strip()
    sessions_query = """
        SELECT
            pid,
            usename,
            datname,
            application_name,
            client_addr,
            client_port,
            backend_start,
            xact_start,
            query_start,
            state_change,
            state,
            wait_event_type,
            wait_event,
            backend_type,
            now() - backend_start AS session_duration,
            CASE WHEN query_start IS NULL THEN NULL ELSE now() - query_start END AS query_duration,
            query
        FROM pg_catalog.pg_stat_activity
        WHERE (%s = '' OR usename ILIKE %s ESCAPE '!')
          AND (%s = '' OR state = %s)
        ORDER BY
            CASE WHEN state = 'active' THEN 0 ELSE 1 END,
            backend_start DESC;
    """

    try:
        rows = _fetch_db_rows(
            db_connection, sessions_query, [username, username_pattern, state, state]
        )
    except Exception as exc:
        return JsonResponse(
            {
                "ok": False,
                "message": f"Не удалось получить активные сессии и подключения: {exc}",
            },
            status=400,
        )

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
                "backend_start": (
                    timezone.localtime(row[6]).strftime("%Y-%m-%d %H:%M:%S")
                    if row[6]
                    else "—"
                ),
                "state": row_state,
                "wait_event": " / ".join([part for part in [row[11], row[12]] if part])
                or "—",
                "backend_type": row[13] or "—",
                "session_duration": (
                    str(session_duration).split(".")[0] if session_duration else "—"
                ),
                "session_duration_seconds": (
                    max(int(session_duration.total_seconds()), 0)
                    if session_duration
                    else 0
                ),
                "query_duration": (
                    str(query_duration).split(".")[0] if query_duration else "—"
                ),
                "query_duration_seconds": (
                    max(int(query_duration.total_seconds()), 0) if query_duration else 0
                ),
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
        "states": [
            {"state": key, "count": value}
            for key, value in sorted(state_counts.items())
        ],
    }
    return JsonResponse(
        {
            "ok": True,
            "sessions": sessions,
            "summary": summary,
            "total_count": len(sessions),
            "username": username,
            "state": state,
        }
    )


@require_http_methods(["POST"])
def terminate_active_session(request):
    """Завершает пользовательскую сессию базы данных."""
    permission_error = _destructive_action_permission_error(request)
    if permission_error:
        return permission_error
    payload = _read_json_body(request)
    db_connection, error_response = _require_payload_connection(request, payload)
    if error_response:
        return error_response

    try:
        pid = int(payload.get("pid"))
        if pid <= 0:
            raise ValueError
    except (TypeError, ValueError):
        return JsonResponse(
            {"ok": False, "message": "Указан некорректный PID сессии"}, status=400
        )

    terminate_query = """
        SELECT
            pg_catalog.pg_terminate_backend(activity.pid),
            activity.pid,
            activity.usename,
            activity.datname,
            activity.application_name,
            activity.client_addr,
            activity.client_port,
            activity.state,
            activity.backend_type,
            activity.backend_start,
            activity.xact_start,
            activity.query_start,
            activity.state_change,
            activity.wait_event_type,
            activity.wait_event,
            now() - activity.backend_start AS session_duration,
            CASE WHEN activity.query_start IS NULL THEN NULL ELSE now() - activity.query_start END AS query_duration,
            activity.query
        FROM pg_catalog.pg_stat_activity AS activity
        WHERE activity.pid = %s
          AND activity.pid <> pg_backend_pid();
    """
    try:
        row = _fetch_db_row(db_connection, terminate_query, [pid])
    except Exception as exc:
        return JsonResponse(
            {"ok": False, "message": f"Не удалось завершить сессию с PID {pid}: {exc}"},
            status=400,
        )

    if not row:
        return JsonResponse(
            {"ok": False, "message": f"Сессия с PID {pid} не найдена"}, status=404
        )
    if not row[0]:
        return JsonResponse(
            {"ok": False, "message": f"Не удалось завершить сессию с PID {pid}"},
            status=409,
        )

    _write_audit(
        "session_terminate",
        _backend_termination_audit_info(
            "Завершение активной сессии", db_connection, row
        ),
        db_user=_current_db_user(request),
    )
    return JsonResponse(
        {"ok": True, "message": f"Сессия с PID {pid} завершена", "pid": pid}
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
    blocking_locks_query = """
        SELECT
            blocked.pid AS blocked_pid,
            blocked.usename AS blocked_user,
            now() - blocked.query_start AS blocked_duration,
            blocked.query AS blocked_query,
            blocker.pid AS blocker_pid,
            blocker.usename AS blocker_user,
            now() - blocker.query_start AS blocker_duration,
            blocker.query AS blocker_query
        FROM pg_catalog.pg_locks AS blocked_locks
        JOIN pg_catalog.pg_stat_activity AS blocked
            ON blocked.pid = blocked_locks.pid
        JOIN pg_catalog.pg_locks AS blocker_locks
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
        JOIN pg_catalog.pg_stat_activity AS blocker
            ON blocker.pid = blocker_locks.pid
        WHERE NOT blocked_locks.granted
          AND blocker_locks.granted
          AND (%s = '' OR blocked.usename = %s)
          AND (%s = '' OR blocker.usename = %s);
    """

    try:
        rows = _fetch_db_rows(
            db_connection,
            blocking_locks_query,
            [blocked_username, blocked_username, blocker_username, blocker_username],
        )
    except Exception as exc:
        return JsonResponse(
            {"ok": False, "message": f"Не удалось получить блокировки: {exc}"},
            status=400,
        )

    locks = []
    for row in rows:
        blocked_duration = row[2]
        blocker_duration = row[6]
        locks.append(
            {
                "blocked_pid": row[0],
                "blocked_user": row[1] or "—",
                "blocked_duration": (
                    str(blocked_duration).split(".")[0] if blocked_duration else "—"
                ),
                "blocked_query": row[3] or "—",
                "blocker_pid": row[4],
                "blocker_user": row[5] or "—",
                "blocker_duration": (
                    str(blocker_duration).split(".")[0] if blocker_duration else "—"
                ),
                "blocker_query": row[7] or "—",
            }
        )
    return JsonResponse(
        {
            "ok": True,
            "locks": locks,
            "total_count": len(locks),
            "blocked_username": blocked_username,
            "blocker_username": blocker_username,
        }
    )


@require_http_methods(["POST"])
def idle_transactions(request):
    """Возвращает простаивающие транзакции выбранного подключения."""
    payload = _read_json_body(request)
    db_connection, error_response = _require_payload_connection(request, payload)
    if error_response:
        return error_response
    username = (payload.get("username") or "").strip()
    idle_transactions_query = """
        SELECT
            pid,
            usename,
            application_name,
            client_addr,
            state,
            now() - xact_start AS transaction_duration,
            now() - state_change AS idle_duration,
            query
        FROM pg_catalog.pg_stat_activity
        WHERE state = 'idle in transaction'
          AND (%s = '' OR usename = %s)
        ORDER BY xact_start;
    """

    try:
        rows = _fetch_db_rows(
            db_connection, idle_transactions_query, [username, username]
        )
    except Exception as exc:
        return JsonResponse(
            {"ok": False, "message": f"Не удалось получить транзакции: {exc}"},
            status=400,
        )

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
                "transaction_duration": (
                    str(transaction_duration).split(".")[0]
                    if transaction_duration
                    else "—"
                ),
                "idle_duration": (
                    str(idle_duration).split(".")[0] if idle_duration else "—"
                ),
                "sql": row[7] or "—",
            }
        )
    return JsonResponse(
        {
            "ok": True,
            "transactions": transactions,
            "total_count": len(transactions),
            "username": username,
        }
    )
