import json

import psycopg2
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_http_methods
from psycopg2 import sql

from db_statistics.models import DBAudit, DBConnection, DBUser

CONNECTION_TIMEOUT_SECONDS = 5
ADMIN_ROLE = "Администратор"
SESSION_USER_ID_KEY = "db_user_id"


def _current_db_user(request):
    user_id = request.session.get(SESSION_USER_ID_KEY)
    if not user_id:
        return None
    try:
        return DBUser.objects.get(pk=user_id, is_active=True)
    except DBUser.DoesNotExist:
        request.session.pop(SESSION_USER_ID_KEY, None)
        return None


def _user_payload(db_user):
    if not db_user:
        return None
    return {"id": db_user.pk, "login": db_user.login, "email": db_user.email, "role": db_user.role, "can_manage_connections": db_user.role == ADMIN_ROLE}


def _connection_permission_error():
    return JsonResponse({"ok": False, "message": "Создавать и редактировать подключения может только Администратор"}, status=403)


def _connection_delete_permission_error():
    return JsonResponse({"ok": False, "message": "Удалять подключение может только его создатель"}, status=403)


def _connection_edit_permission_error():
    return JsonResponse({"ok": False, "message": "Редактировать подключение может только его создатель"}, status=403)


def _audit_username(db_user=None, fallback="Неизвестный пользователь"):
    if db_user:
        return db_user.login
    return fallback


def _write_audit(action_type, info, db_user=None, username=None):
    DBAudit.objects.create(username=username or _audit_username(db_user), action_type=action_type, info=info, created=timezone.now())


def _audit_action_label(action_type):
    return dict(DBAudit.ACTION_TYPES).get(action_type, action_type)


def _connection_audit_info(action, connection, *, result=None, error=None):
    details = [f"Действие: {action}", f"Подключение: {connection.name}", f"Тип БД: {connection.db_type}", f"Хост: {connection.host}", f"Порт: {connection.port}", f"База данных: {connection.database}", f"Пользователь БД: {connection.username}"]
    if result:
        details.append(f"Результат: {result}")
    if error:
        details.append(f"Ошибка: {error}")
    return "; ".join(details)


def _can_manage_connections(request):
    db_user = _current_db_user(request)
    return bool(db_user and db_user.role == ADMIN_ROLE)


def _available_connections(request):
    db_user = _current_db_user(request)
    if not db_user:
        return DBConnection.objects.none()
    return db_user.connections.filter(is_active=True).select_related("created_user")


def _get_connection_for_request(request, connection_id):
    return get_object_or_404(_available_connections(request), pk=connection_id)


@ensure_csrf_cookie
def home(request):
    """Главная страница мониторинга БД."""
    db_user = _current_db_user(request)
    if not db_user:
        return redirect("login")
    return render(request, "home.html", {"db_user": db_user, "db_user_json": json.dumps(_user_payload(db_user), ensure_ascii=False), "user_can_manage_connections": db_user.role == ADMIN_ROLE})


@ensure_csrf_cookie
@require_http_methods(["GET", "POST"])
def login(request):
    db_user = _current_db_user(request)
    if db_user:
        return redirect("home")

    error = ""
    login_value = ""
    email_value = ""
    if request.method == "POST":
        login_value = (request.POST.get("login") or "").strip()
        email_value = (request.POST.get("email") or "").strip()
        db_user = DBUser.objects.filter(login=login_value, email=email_value, is_active=True).first()
        if db_user:
            request.session[SESSION_USER_ID_KEY] = db_user.pk
            _write_audit("login", f"Пользователь вошёл в приложение: login={db_user.login}; email={db_user.email}; role={db_user.role}", db_user=db_user)
            return redirect("home")
        error = "Пользователь с указанными login и email не найден или отключён"

    return render(request, "login.html", {"error": error, "login_value": login_value, "email_value": email_value})


@require_http_methods(["POST"])
def logout(request):
    db_user = _current_db_user(request)
    username = _audit_username(db_user)
    if db_user:
        audit_info = f"Пользователь вышел из приложения: login={db_user.login}; email={db_user.email}; role={db_user.role}"
    else:
        audit_info = "Выход из приложения: активный пользователь не найден"
    _write_audit("logout", audit_info, db_user=db_user, username=username)
    request.session.flush()
    return redirect("login")


@require_http_methods(["GET"])
def audit_events(request):
    db_user = _current_db_user(request)
    if not db_user:
        return JsonResponse({"ok": False, "message": "Требуется вход в приложение"}, status=401)

    action_type = (request.GET.get("action_type") or "").strip()
    available_actions = [{"value": value, "label": label} for value, label in DBAudit.ACTION_TYPES]

    audit_queryset = DBAudit.objects.filter(username=db_user.login)
    if action_type:
        valid_action_types = {value for value, _label in DBAudit.ACTION_TYPES}
        if action_type not in valid_action_types:
            return JsonResponse({"ok": False, "message": "Неизвестный тип действия"}, status=400)
        audit_queryset = audit_queryset.filter(action_type=action_type)

    page_size = 100
    page = max(int(request.GET.get("page") or 1), 1)
    offset = (page - 1) * page_size
    total_count = audit_queryset.count()
    events = [
        {"id": audit.pk, "username": audit.username, "action_type": audit.action_type, "action_label": _audit_action_label(audit.action_type), "info": audit.info, "created": timezone.localtime(audit.created).strftime("%Y-%m-%d %H:%M:%S")}
        for audit in audit_queryset[offset : offset + page_size]
    ]
    return JsonResponse({"ok": True, "events": events, "actions": available_actions, "page": page, "page_size": page_size, "total_count": total_count})


def _connection_to_dict(connection):
    return {
        "id": str(connection.pk),
        "name": connection.name,
        "host": connection.host,
        "port": connection.port,
        "database": connection.database,
        "user": connection.username,
        "db_type": connection.db_type,
        "created_by": connection.created_user.login if connection.created_user else None,
        "created_by_id": connection.created_user_id,
        "status": "offline",
    }


def _read_json_body(request):
    try:
        return json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return {}


def _parse_pg_size_to_bytes(value):
    if value in (None, ""):
        return None
    text = str(value).strip()
    if not text:
        return None
    parts = text.split()
    if len(parts) == 1:
        number_part = "".join(ch for ch in text if ch.isdigit() or ch in ".,-")
        unit_part = text[len(number_part) :].strip() or "B"
    else:
        number_part, unit_part = parts[0], parts[1]
    try:
        number = float(number_part.replace(",", "."))
    except ValueError:
        return None
    unit = unit_part.lower()
    multipliers = {"b": 1, "byte": 1, "bytes": 1, "kb": 1024, "kib": 1024, "mb": 1024**2, "mib": 1024**2, "gb": 1024**3, "gib": 1024**3, "tb": 1024**4, "tib": 1024**4}
    return int(number * multipliers.get(unit, 1))


def _format_bytes(size_bytes):
    if size_bytes is None:
        return "—"
    value = float(size_bytes)
    for unit in ["Б", "КБ", "МБ", "ГБ"]:
        if value < 1024:
            return f"{value:.2f} {unit}"
        value /= 1024
    return f"{value:.2f} ТБ"


def _escape_like_pattern(value):
    return value.replace("!", "!!").replace("%", "!%").replace("_", "!_")


def _connection_kwargs(host, port, database, username, password, ssl=True):
    return {"host": host, "port": port, "dbname": database, "user": username, "password": password, "connect_timeout": CONNECTION_TIMEOUT_SECONDS, "sslmode": "prefer" if ssl else "disable"}


def _test_connection_params(host, port, database, username, password, ssl):
    with psycopg2.connect(**_connection_kwargs(host, port, database, username, password, ssl)) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()


def _open_database_connection(db_connection, ssl=True):
    return psycopg2.connect(**_connection_kwargs(db_connection.host, db_connection.port, db_connection.database, db_connection.username, db_connection.get_password(), ssl))


def _fetch_db_rows(db_connection, query, params=None):
    with _open_database_connection(db_connection) as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, params or [])
            return cursor.fetchall()


def _fetch_db_row(db_connection, query, params=None):
    with _open_database_connection(db_connection) as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, params or [])
            return cursor.fetchone()


def _fetch_db_resultsets(db_connection, *queries):
    resultsets = []
    with _open_database_connection(db_connection) as connection:
        with connection.cursor() as cursor:
            for query, params in queries:
                cursor.execute(query, params or [])
                resultsets.append(cursor.fetchall())
    return resultsets


def _require_payload_connection(request, payload):
    connection_id = payload.get("id")
    if not connection_id:
        return None, JsonResponse({"ok": False, "message": "Подключение не выбрано"}, status=400)
    return _get_connection_for_request(request, connection_id), None


@require_http_methods(["GET", "POST"])
def connections(request):
    if request.method == "GET":
        items = _available_connections(request).order_by("name", "host")
        return JsonResponse({"connections": [_connection_to_dict(item) for item in items]})

    if not _can_manage_connections(request):
        return _connection_permission_error()

    payload = _read_json_body(request)
    required_fields = ["name", "host", "port", "database", "user"]
    if any(not payload.get(field) for field in required_fields):
        return JsonResponse({"ok": False, "message": "Заполните все обязательные поля"}, status=400)

    defaults = {"username": payload["user"].strip(), "db_type": payload.get("db_type") or "PostgreSQL", "is_active": True}
    if payload.get("password"):
        defaults["password"] = payload["password"]

    db_user = _current_db_user(request)

    if payload.get("id"):
        connection = _get_connection_for_request(request, payload["id"])
        if not db_user or connection.created_user_id != db_user.pk:
            return _connection_edit_permission_error()
        connection.name = payload["name"].strip()
        connection.host = payload["host"].strip()
        connection.port = int(payload["port"])
        connection.database = payload["database"].strip()
        for field, value in defaults.items():
            setattr(connection, field, value)
        connection.save()
        _write_audit("connection_update", _connection_audit_info("Изменение подключения", connection), db_user=_current_db_user(request))
        return JsonResponse({"ok": True, "created": False, "connection": _connection_to_dict(connection)})

    connection, created = DBConnection.objects.update_or_create(name=payload["name"].strip(), host=payload["host"].strip(), port=int(payload["port"]), database=payload["database"].strip(), defaults={**defaults, "password": payload.get("password", "")})
    if db_user:
        if created or connection.created_user_id is None:
            connection.created_user = db_user
            connection.save(update_fields=["created_user", "updated"])
        db_user.connections.add(connection)
    _write_audit("connection_create" if created else "connection_update", _connection_audit_info("Создание подключения" if created else "Изменение подключения", connection), db_user=db_user)
    return JsonResponse({"ok": True, "created": created, "connection": _connection_to_dict(connection)}, status=201 if created else 200)


@require_http_methods(["POST"])
def test_connection(request):
    payload = _read_json_body(request)
    connection_id = payload.get("id")
    has_inline_connection_data = all(payload.get(field) for field in ["name", "host", "port", "database", "user"])
    if (not connection_id or has_inline_connection_data) and not _can_manage_connections(request):
        return _connection_permission_error()

    if connection_id:
        connection = _get_connection_for_request(request, connection_id)
        if has_inline_connection_data:
            params = {"host": payload["host"].strip(), "port": int(payload["port"]), "database": payload["database"].strip(), "username": payload["user"].strip(), "password": payload.get("password") or connection.get_password(), "ssl": payload.get("ssl", True)}
            name = payload["name"].strip()
        else:
            params = {"host": connection.host, "port": connection.port, "database": connection.database, "username": connection.username, "password": connection.get_password(), "ssl": payload.get("ssl", True)}
            name = connection.name
    else:
        required_fields = ["name", "host", "port", "database", "user"]
        if any(not payload.get(field) for field in required_fields):
            return JsonResponse({"ok": False, "message": "Заполните все обязательные поля"}, status=400)
        params = {"host": payload["host"].strip(), "port": int(payload["port"]), "database": payload["database"].strip(), "username": payload["user"].strip(), "password": payload.get("password", ""), "ssl": payload.get("ssl", True)}
        name = payload["name"].strip()

    audit_user = _current_db_user(request)
    audit_connection = connection if connection_id else None
    try:
        _test_connection_params(**params)
    except Exception as exc:
        if audit_connection:
            info = _connection_audit_info("Проверка подключения", audit_connection, result="Ошибка", error=exc)
        else:
            info = f"Действие: Проверка нового подключения; Подключение: {name}; " f"Хост: {params['host']}; Порт: {params['port']}; База данных: {params['database']}; " f"Пользователь БД: {params['username']}; Результат: Ошибка; Ошибка: {exc}"
        _write_audit("connection_test", info, db_user=audit_user)
        return JsonResponse({"ok": False, "message": f"Не удалось подключиться к {name}: {exc}"}, status=400)

    if audit_connection:
        info = _connection_audit_info("Проверка подключения", audit_connection, result="Успешно")
    else:
        info = f"Действие: Проверка нового подключения; Подключение: {name}; " f"Хост: {params['host']}; Порт: {params['port']}; База данных: {params['database']}; " f"Пользователь БД: {params['username']}; Результат: Успешно"
    _write_audit("connection_test", info, db_user=audit_user)
    return JsonResponse({"ok": True, "message": f"Подключение к {name} успешно"})


@require_http_methods(["POST"])
def delete_connection(request):
    if not _can_manage_connections(request):
        return _connection_permission_error()

    payload = _read_json_body(request)
    connection_id = payload.get("id")
    if not connection_id:
        return JsonResponse({"ok": False, "message": "Подключение не выбрано"}, status=400)

    connection = _get_connection_for_request(request, connection_id)
    db_user = _current_db_user(request)
    if not db_user or connection.created_user_id != db_user.pk:
        return _connection_delete_permission_error()

    audit_info = _connection_audit_info("Удаление подключения", connection)
    connection.is_active = False
    connection.save(update_fields=["is_active", "updated"])
    _write_audit("connection_delete", audit_info, db_user=db_user)
    return JsonResponse({"ok": True, "message": f"Подключение {connection.name} удалено"})


@require_http_methods(["POST"])
def database_overview(request):
    payload = _read_json_body(request)
    db_connection, error_response = _require_payload_connection(request, payload)
    if error_response:
        return error_response
    overview_query = """
        WITH relation_sizes AS (
            SELECT
                table_class.oid,
                table_class.relkind,
                table_class.relpersistence,
                namespace.nspname,
                pg_total_relation_size(table_class.oid)::bigint AS total_size_bytes,
                CASE
                    WHEN table_class.relkind IN ('r', 'p', 'm')
                    THEN pg_indexes_size(table_class.oid)::bigint
                    ELSE 0::bigint
                END AS index_size_bytes
            FROM pg_catalog.pg_class AS table_class
            JOIN pg_catalog.pg_namespace AS namespace
                ON namespace.oid = table_class.relnamespace
            WHERE table_class.relkind IN ('r', 'p', 'm')
              AND namespace.nspname NOT IN ('pg_catalog', 'information_schema', 'gp_toolkit')
              AND namespace.nspname NOT LIKE 'pg_toast%%'
        )
        SELECT
            version() AS database_version,
            current_setting('statement_mem', true) AS statement_mem,
            current_setting('max_statement_mem', true) AS max_statement_mem,
            current_setting('gp_vmem_protect_limit', true) AS gp_vmem_protect_limit,
            pg_database_size(%s)::bigint AS total_size_bytes,
            COALESCE(SUM(index_size_bytes), 0)::bigint AS index_size_bytes,
            GREATEST(pg_database_size(%s)::bigint - COALESCE(SUM(index_size_bytes), 0)::bigint, 0)::bigint AS data_size_without_indexes_bytes,
            COALESCE(SUM(total_size_bytes) FILTER (WHERE relpersistence = 't' OR nspname LIKE 'pg_temp_%%'), 0)::bigint AS temp_table_size_bytes,
            COALESCE(SUM(total_size_bytes) FILTER (WHERE relkind = 'm'), 0)::bigint AS materialized_view_size_bytes,
            (SELECT COUNT(*) FROM pg_catalog.pg_roles WHERE rolcanlogin)::bigint AS user_count,
            (SELECT COUNT(*) FROM pg_catalog.pg_roles WHERE NOT rolcanlogin)::bigint AS group_count,
            (SELECT COUNT(*) FROM pg_catalog.pg_stat_activity)::bigint AS current_connections,
            (SELECT setting::int FROM pg_catalog.pg_settings WHERE name = 'max_connections') AS max_connections,
            (
                SELECT ROUND(COUNT(*) * 100.0 / setting::int, 2)
                FROM pg_catalog.pg_stat_activity, pg_catalog.pg_settings
                WHERE name = 'max_connections'
                GROUP BY setting
            ) AS connection_usage_percent,
            pg_postmaster_start_time() AS server_started_at,
            date_trunc('second', now() - pg_postmaster_start_time()) AS server_uptime,
            current_setting('server_version', true) AS server_version,
            current_setting('server_encoding', true) AS server_encoding,
            current_setting('TimeZone', true) AS timezone,
            current_setting('superuser_reserved_connections', true) AS superuser_reserved_connections,
            current_setting('statement_timeout', true) AS statement_timeout,
            current_setting('lock_timeout', true) AS lock_timeout,
            current_setting('idle_in_transaction_session_timeout', true) AS idle_in_transaction_session_timeout,
            current_setting('default_transaction_isolation', true) AS default_transaction_isolation,
            current_setting('DateStyle', true) AS date_style
        FROM relation_sizes;
    """

    try:
        row = _fetch_db_row(db_connection, overview_query, [db_connection.database, db_connection.database])
    except Exception as exc:
        return JsonResponse({"ok": False, "message": f"Не удалось получить обзор БД: {exc}"}, status=400)

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
            "basic_settings": basic_settings,
        }
    )


@require_http_methods(["POST"])
def active_queries(request):
    payload = _read_json_body(request)
    db_connection, error_response = _require_payload_connection(request, payload)
    if error_response:
        return error_response
    username = (payload.get("username") or "").strip()
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
          AND (%s = '' OR activity.usename = %s)
        ORDER BY duration DESC;
    """

    try:
        rows = _fetch_db_rows(db_connection, active_queries_query, [username, username])
    except Exception as exc:
        return JsonResponse({"ok": False, "message": f"Не удалось получить активные запросы: {exc}"}, status=400)

    queries = []
    for row in rows:
        duration = row[4]
        queries.append(
            {"pid": row[0], "username": row[1] or "—", "relation_name": row[2] or "—", "state": row[3] or "—", "duration": str(duration).split(".")[0] if duration else "—", "duration_seconds": max(int(duration.total_seconds()), 0) if duration else 0, "sql": row[5] or "—"}
        )
    return JsonResponse({"ok": True, "queries": queries, "total_count": len(queries), "username": username})


@require_http_methods(["POST"])
def blocking_locks(request):
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
        rows = _fetch_db_rows(db_connection, blocking_locks_query, [blocked_username, blocked_username, blocker_username, blocker_username])
    except Exception as exc:
        return JsonResponse({"ok": False, "message": f"Не удалось получить блокировки: {exc}"}, status=400)

    locks = []
    for row in rows:
        blocked_duration = row[2]
        blocker_duration = row[6]
        locks.append(
            {
                "blocked_pid": row[0],
                "blocked_user": row[1] or "—",
                "blocked_duration": str(blocked_duration).split(".")[0] if blocked_duration else "—",
                "blocked_query": row[3] or "—",
                "blocker_pid": row[4],
                "blocker_user": row[5] or "—",
                "blocker_duration": str(blocker_duration).split(".")[0] if blocker_duration else "—",
                "blocker_query": row[7] or "—",
            }
        )
    return JsonResponse({"ok": True, "locks": locks, "total_count": len(locks), "blocked_username": blocked_username, "blocker_username": blocker_username})


@require_http_methods(["POST"])
def idle_transactions(request):
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
        rows = _fetch_db_rows(db_connection, idle_transactions_query, [username, username])
    except Exception as exc:
        return JsonResponse({"ok": False, "message": f"Не удалось получить транзакции: {exc}"}, status=400)

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
                "transaction_duration": str(transaction_duration).split(".")[0] if transaction_duration else "—",
                "idle_duration": str(idle_duration).split(".")[0] if idle_duration else "—",
                "sql": row[7] or "—",
            }
        )
    return JsonResponse({"ok": True, "transactions": transactions, "total_count": len(transactions), "username": username})


@require_http_methods(["POST"])
def database_activity(request):
    payload = _read_json_body(request)
    db_connection, error_response = _require_payload_connection(request, payload)
    if error_response:
        return error_response

    activity_query = """
        SELECT
            datname,
            xact_commit::bigint,
            xact_rollback::bigint,
            (xact_commit + xact_rollback)::bigint AS total_xacts,
            ROUND(xact_rollback::numeric / NULLIF(xact_commit + xact_rollback, 0) * 100, 2) AS rollback_percent,
            blks_read::bigint,
            blks_hit::bigint,
            ROUND(blks_hit::numeric / NULLIF(blks_hit + blks_read, 0) * 100, 2) AS cache_hit_percent,
            deadlocks::bigint,
            temp_files::bigint,
            temp_bytes::bigint
        FROM pg_catalog.pg_stat_database
        WHERE datname IS NOT NULL
        ORDER BY (xact_commit + xact_rollback) DESC;
    """
    client_activity_query = """
        SELECT
            datname,
            COUNT(*)::bigint AS sessions_total,
            COUNT(*) FILTER (WHERE state = 'active')::bigint AS active_sessions,
            COUNT(*) FILTER (WHERE state = 'idle')::bigint AS idle_sessions,
            COUNT(*) FILTER (WHERE state = 'idle in transaction')::bigint AS idle_in_transaction_sessions,
            COUNT(*) FILTER (WHERE wait_event_type IS NOT NULL)::bigint AS waiting_sessions,
            COUNT(*) FILTER (WHERE backend_type = 'client backend')::bigint AS client_backends
        FROM pg_catalog.pg_stat_activity
        GROUP BY datname
        ORDER BY sessions_total DESC;
    """
    wait_events_query = """
        SELECT
            COALESCE(wait_event_type, 'Без ожидания') AS wait_event_type,
            COALESCE(wait_event, '—') AS wait_event,
            COUNT(*)::bigint AS sessions_count
        FROM pg_catalog.pg_stat_activity
        WHERE backend_type = 'client backend'
        GROUP BY wait_event_type, wait_event
        ORDER BY sessions_count DESC, wait_event_type
        LIMIT 20;
    """

    try:
        activity_rows, client_rows, wait_rows = _fetch_db_resultsets(
            db_connection,
            (activity_query, []),
            (client_activity_query, []),
            (wait_events_query, []),
        )
    except Exception as exc:
        return JsonResponse({"ok": False, "message": f"Не удалось получить активность БД: {exc}"}, status=400)

    databases = []
    for row in activity_rows:
        databases.append({
            "database": row[0] or "—",
            "commits": int(row[1] or 0),
            "rollbacks": int(row[2] or 0),
            "total_transactions": int(row[3] or 0),
            "rollback_percent": float(row[4] or 0),
            "blocks_read": int(row[5] or 0),
            "blocks_hit": int(row[6] or 0),
            "cache_hit_percent": float(row[7] or 0),
            "deadlocks": int(row[8] or 0),
            "temp_files": int(row[9] or 0),
            "temp_bytes": int(row[10] or 0),
            "temp_size": _format_bytes(int(row[10] or 0)),
        })

    sessions = []
    for row in client_rows:
        sessions.append({
            "database": row[0] or "Фоновые процессы",
            "sessions_total": int(row[1] or 0),
            "active_sessions": int(row[2] or 0),
            "idle_sessions": int(row[3] or 0),
            "idle_in_transaction_sessions": int(row[4] or 0),
            "waiting_sessions": int(row[5] or 0),
            "client_backends": int(row[6] or 0),
        })

    waits = [{"wait_event_type": row[0] or "—", "wait_event": row[1] or "—", "sessions_count": int(row[2] or 0)} for row in wait_rows]
    totals = {
        "total_transactions": sum(item["total_transactions"] for item in databases),
        "rollbacks": sum(item["rollbacks"] for item in databases),
        "active_sessions": sum(item["active_sessions"] for item in sessions),
        "waiting_sessions": sum(item["waiting_sessions"] for item in sessions),
    }
    totals["rollback_percent"] = round(totals["rollbacks"] / totals["total_transactions"] * 100, 2) if totals["total_transactions"] else 0

    return JsonResponse({"ok": True, "databases": databases, "sessions": sessions, "wait_events": waits, "totals": totals})


@require_http_methods(["POST"])
def memory_overview(request):
    payload = _read_json_body(request)
    db_connection, error_response = _require_payload_connection(request, payload)
    if error_response:
        return error_response
    memory_query = """
        WITH relation_sizes AS (
            SELECT
                table_class.oid,
                table_class.relkind,
                table_class.relpersistence,
                namespace.nspname,
                pg_total_relation_size(table_class.oid)::bigint AS total_size_bytes,
                CASE
                    WHEN table_class.relkind IN ('r', 'p', 'm')
                    THEN pg_indexes_size(table_class.oid)::bigint
                    ELSE 0::bigint
                END AS index_size_bytes
            FROM pg_catalog.pg_class AS table_class
            JOIN pg_catalog.pg_namespace AS namespace
                ON namespace.oid = table_class.relnamespace
            WHERE table_class.relkind IN ('r', 'p', 'm')
              AND namespace.nspname NOT IN ('pg_catalog', 'information_schema', 'gp_toolkit')
              AND namespace.nspname NOT LIKE 'pg_toast%%'
        )
        SELECT
            current_setting('gp_vmem_protect_limit', true) AS gp_vmem_protect_limit,
            current_setting('shared_buffers', true) AS shared_buffers,
            current_setting('work_mem', true) AS work_mem,
            current_setting('maintenance_work_mem', true) AS maintenance_work_mem,
            current_setting('statement_mem', true) AS statement_mem,
            current_setting('max_statement_mem', true) AS max_statement_mem,
            pg_database_size(%s)::bigint AS total_size_bytes,
            COALESCE(SUM(index_size_bytes), 0)::bigint AS index_size_bytes,
            GREATEST(pg_database_size(%s)::bigint - COALESCE(SUM(index_size_bytes), 0)::bigint, 0)::bigint AS data_size_without_indexes_bytes,
            COALESCE(SUM(total_size_bytes) FILTER (WHERE relpersistence = 't' OR nspname LIKE 'pg_temp_%%'), 0)::bigint AS temp_table_size_bytes,
            COALESCE(SUM(total_size_bytes) FILTER (WHERE relkind = 'm'), 0)::bigint AS materialized_view_size_bytes
        FROM relation_sizes;
    """

    try:
        row = _fetch_db_row(db_connection, memory_query, [db_connection.database, db_connection.database])
    except Exception as exc:
        return JsonResponse({"ok": False, "message": f"Не удалось получить параметры памяти: {exc}"}, status=400)

    settings = [
        {"key": "gp_vmem_protect_limit", "label": "Лимит виртуальной памяти сегмента", "value": row[0] or "—", "role": "Защита OOM"},
        {"key": "shared_buffers", "label": "Кэш данных", "value": row[1] or "—", "role": "Буферы"},
        {"key": "work_mem", "label": "Память операций", "value": row[2] or "—", "role": "Сортировка/Hash"},
        {"key": "maintenance_work_mem", "label": "Память обслуживания", "value": row[3] or "—", "role": "Очистка / создание индекса"},
        {"key": "statement_mem", "label": "Память запроса", "value": row[4] or "—", "role": "Лимит запроса"},
        {"key": "max_statement_mem", "label": "Максимальная память запроса", "value": row[5] or "—", "role": "Макс. лимит"},
    ]

    sizes = {
        "gp_vmem_protect_limit": _parse_pg_size_to_bytes(row[0]),
        "shared_buffers": _parse_pg_size_to_bytes(row[1]),
        "work_mem": _parse_pg_size_to_bytes(row[2]),
        "maintenance_work_mem": _parse_pg_size_to_bytes(row[3]),
        "statement_mem": _parse_pg_size_to_bytes(row[4]),
        "max_statement_mem": _parse_pg_size_to_bytes(row[5]),
    }

    def usage_row(label, used_key, limit_key):
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


def _format_role_timestamp(value):
    if value is None:
        return "Бессрочно"
    return value.strftime("%Y-%m-%d %H:%M:%S") if hasattr(value, "strftime") else str(value)


def _role_flag(value):
    return "Да" if value else "Нет"


def _database_roles_list(request, *, can_login):
    payload = _read_json_body(request)
    db_connection, error_response = _require_payload_connection(request, payload)
    if error_response:
        return error_response
    page_size = int(payload.get("page_size") or (100 if can_login else 10000))
    page = max(int(payload.get("page") or 1), 1)
    offset = (page - 1) * page_size
    search = (payload.get("search") or "").strip()
    sort = payload.get("sort") or "name"
    direction = "ASC" if payload.get("direction") == "asc" else "DESC"
    sort_columns = {"name": "name", "superuser": "superuser", "createdb": "createdb", "createrole": "createrole", "inherit": "inherit", "replication": "replication", "connection_limit": "connection_limit", "valid_until": "valid_until", "member_count": "member_count"}
    sort_column = sort_columns.get(sort, "name")
    role_type_message = "пользователей" if can_login else "групп"

    where_sql = ""
    params = [can_login]
    if search:
        where_sql = "AND role_info.rolname ILIKE %s ESCAPE '!'"
        params.append(f"%{_escape_like_pattern(search)}%")

    roles_query = f"""
        WITH roles AS (
            SELECT
                role_info.rolname AS name,
                role_info.rolsuper AS superuser,
                role_info.rolcreatedb AS createdb,
                role_info.rolcreaterole AS createrole,
                role_info.rolinherit AS inherit,
                role_info.rolreplication AS replication,
                role_info.rolconnlimit AS connection_limit,
                role_info.rolvaliduntil AS valid_until,
                COUNT(membership.member)::bigint AS member_count
            FROM pg_catalog.pg_roles AS role_info
            LEFT JOIN pg_catalog.pg_auth_members AS membership
                ON membership.roleid = role_info.oid
            WHERE role_info.rolcanlogin = %s
              {where_sql}
            GROUP BY
                role_info.rolname,
                role_info.rolsuper,
                role_info.rolcreatedb,
                role_info.rolcreaterole,
                role_info.rolinherit,
                role_info.rolreplication,
                role_info.rolconnlimit,
                role_info.rolvaliduntil
        )
        SELECT
            name,
            superuser,
            createdb,
            createrole,
            inherit,
            replication,
            connection_limit,
            valid_until,
            member_count,
            COUNT(*) OVER() AS total_count,
            SUM(CASE WHEN superuser THEN 1 ELSE 0 END) OVER() AS superuser_count,
            SUM(CASE WHEN createdb THEN 1 ELSE 0 END) OVER() AS createdb_count,
            SUM(CASE WHEN replication THEN 1 ELSE 0 END) OVER() AS replication_count,
            SUM(CASE WHEN superuser OR createdb OR createrole OR replication THEN 1 ELSE 0 END) OVER() AS privileged_count
        FROM roles
        ORDER BY {sort_column} {direction}, name ASC
        LIMIT %s OFFSET %s;
    """

    try:
        rows = _fetch_db_rows(db_connection, roles_query, [*params, page_size, offset])
    except Exception as exc:
        return JsonResponse({"ok": False, "message": f"Не удалось получить список {role_type_message}: {exc}"}, status=400)

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


@require_http_methods(["POST"])
def database_users_list(request):
    return _database_roles_list(request, can_login=True)


@require_http_methods(["POST"])
def database_groups_list(request):
    return _database_roles_list(request, can_login=False)


@require_http_methods(["POST"])
def maintenance_stats(request):
    payload = _read_json_body(request)
    db_connection, error_response = _require_payload_connection(request, payload)
    if error_response:
        return error_response
    page_size = 100
    page = max(int(payload.get("page") or 1), 1)
    offset = (page - 1) * page_size
    search = (payload.get("search") or "").strip()
    sort = payload.get("sort") or "dead_rows"
    direction = "ASC" if payload.get("direction") == "asc" else "DESC"
    sort_columns = {"schema_name": "schemaname", "table_name": "relname", "live_rows": "live_rows", "dead_rows": "dead_rows", "dead_percent": "dead_percent", "last_vacuum": "last_vacuum_at", "last_analyze": "last_analyze_at"}
    sort_column = sort_columns.get(sort, "dead_rows")
    where_sql = ""
    params = []
    if search:
        search_pattern = f"%{_escape_like_pattern(search)}%"
        where_sql = "WHERE schemaname ILIKE %s ESCAPE '!' OR relname ILIKE %s ESCAPE '!'"
        params.extend([search_pattern, search_pattern])

    maintenance_query = f"""
        WITH maintenance AS (
            SELECT
                schemaname,
                relname,
                COALESCE(n_live_tup, 0)::bigint AS live_rows,
                COALESCE(n_dead_tup, 0)::bigint AS dead_rows,
                CASE
                    WHEN COALESCE(n_live_tup, 0) + COALESCE(n_dead_tup, 0) = 0 THEN 0
                    ELSE ROUND(COALESCE(n_dead_tup, 0) * 100.0 / (COALESCE(n_live_tup, 0) + COALESCE(n_dead_tup, 0)), 2)
                END AS dead_percent,
                CASE
                    WHEN last_vacuum IS NULL THEN last_autovacuum
                    WHEN last_autovacuum IS NULL THEN last_vacuum
                    ELSE GREATEST(last_vacuum, last_autovacuum)
                END AS last_vacuum_at,
                CASE
                    WHEN last_analyze IS NULL THEN last_autoanalyze
                    WHEN last_autoanalyze IS NULL THEN last_analyze
                    ELSE GREATEST(last_analyze, last_autoanalyze)
                END AS last_analyze_at
            FROM pg_catalog.pg_stat_user_tables
        )
        SELECT
            schemaname,
            relname,
            live_rows,
            dead_rows,
            dead_percent,
            last_vacuum_at,
            last_analyze_at,
            COUNT(*) OVER() AS total_count
        FROM maintenance
        {where_sql}
        ORDER BY {sort_column} {direction}, schemaname ASC, relname ASC
        LIMIT %s OFFSET %s;
    """

    try:
        rows = _fetch_db_rows(db_connection, maintenance_query, [*params, page_size, offset])
    except Exception as exc:
        return JsonResponse({"ok": False, "message": f"Не удалось получить статистику обслуживания: {exc}"}, status=400)

    def format_datetime(value):
        return value.strftime("%Y-%m-%d %H:%M:%S") if value else "Никогда"

    tables = [{"schema_name": row[0], "table_name": row[1], "live_rows": int(row[2] or 0), "dead_rows": int(row[3] or 0), "dead_percent": float(row[4] or 0), "last_vacuum": format_datetime(row[5]), "last_analyze": format_datetime(row[6])} for row in rows]
    total_count = int(rows[0][7]) if rows else 0
    return JsonResponse({"ok": True, "tables": tables, "page": page, "page_size": page_size, "total_count": total_count})


@require_http_methods(["POST"])
def database_schema_sizes(request):
    payload = _read_json_body(request)
    db_connection, error_response = _require_payload_connection(request, payload)
    if error_response:
        return error_response
    page_size = 100
    page = max(int(payload.get("page") or 1), 1)
    offset = (page - 1) * page_size
    search = (payload.get("search") or "").strip()
    sort = payload.get("sort") or "size_bytes"
    direction = "ASC" if payload.get("direction") == "asc" else "DESC"
    sort_columns = {"schema_name": "schema_name", "schema_owner": "schema_owner", "table_count": "table_count", "size_bytes": "size_bytes"}
    sort_column = sort_columns.get(sort, "size_bytes")

    where_sql = ""
    params = []
    if search:
        where_sql = "AND (namespace.nspname ILIKE %s OR owner.rolname ILIKE %s)"
        params.extend([f"%{search}%", f"%{search}%"])

    schema_sizes_query = f"""
        WITH schema_sizes AS (
            SELECT
                namespace.nspname AS schema_name,
                COALESCE(owner.rolname, '-') AS schema_owner,
                COUNT(table_class.oid)::bigint AS table_count,
                SUM(pg_total_relation_size(table_class.oid))::bigint AS size_bytes
            FROM pg_catalog.pg_class AS table_class
            JOIN pg_catalog.pg_namespace AS namespace
                ON namespace.oid = table_class.relnamespace
            LEFT JOIN pg_catalog.pg_roles AS owner
                ON owner.oid = namespace.nspowner
            WHERE table_class.relkind IN ('r', 'p', 'm')
              AND namespace.nspname NOT IN ('pg_catalog', 'information_schema', 'gp_toolkit')
              AND namespace.nspname NOT LIKE 'pg_toast%%'
              {where_sql}
            GROUP BY namespace.nspname, owner.rolname
        )
        SELECT
            schema_name,
            schema_owner,
            table_count,
            size_bytes,
            pg_size_pretty(size_bytes) AS table_size,
            COUNT(*) OVER() AS total_count
        FROM schema_sizes
        ORDER BY {sort_column} {direction}, schema_name ASC
        LIMIT %s OFFSET %s;
    """

    schema_distribution_query = f"""
        WITH schema_sizes AS (
            SELECT
                namespace.nspname AS schema_name,
                SUM(pg_total_relation_size(table_class.oid))::bigint AS size_bytes
            FROM pg_catalog.pg_class AS table_class
            JOIN pg_catalog.pg_namespace AS namespace
                ON namespace.oid = table_class.relnamespace
            LEFT JOIN pg_catalog.pg_roles AS owner
                ON owner.oid = namespace.nspowner
            WHERE table_class.relkind IN ('r', 'p', 'm')
              AND namespace.nspname NOT IN ('pg_catalog', 'information_schema', 'gp_toolkit')
              AND namespace.nspname NOT LIKE 'pg_toast%%'
              {where_sql}
            GROUP BY namespace.nspname
        )
        SELECT
            schema_name,
            size_bytes,
            pg_size_pretty(size_bytes) AS table_size
        FROM schema_sizes
        ORDER BY size_bytes DESC, schema_name ASC;
    """

    try:
        rows, distribution_rows = _fetch_db_resultsets(db_connection, (schema_sizes_query, [*params, page_size, offset]), (schema_distribution_query, params))
    except Exception as exc:
        return JsonResponse({"ok": False, "message": f"Не удалось получить размеры схем: {exc}"}, status=400)

    schemas = [{"schema_name": row[0], "schema_owner": row[1], "table_count": int(row[2]), "size_bytes": int(row[3]), "table_size": row[4]} for row in rows]
    schema_distribution = [{"schema_name": row[0], "size_bytes": int(row[1] or 0), "table_size": row[2]} for row in distribution_rows]
    total_count = int(rows[0][5]) if rows else len(schema_distribution)
    return JsonResponse({"ok": True, "schemas": schemas, "schema_distribution": schema_distribution, "page": page, "page_size": page_size, "total_count": total_count})


@require_http_methods(["POST"])
def database_table_sizes(request):
    payload = _read_json_body(request)
    db_connection, error_response = _require_payload_connection(request, payload)
    if error_response:
        return error_response
    page_size = 100
    page = max(int(payload.get("page") or 1), 1)
    offset = (page - 1) * page_size
    search = (payload.get("search") or "").strip()
    sort = payload.get("sort") or "size_bytes"
    direction = "ASC" if payload.get("direction") == "asc" else "DESC"
    sort_columns = {"schema_name": "schema_name", "table_name": "table_name", "table_owner": "table_owner", "size_bytes": "size_bytes", "index_size_bytes": "index_size_bytes", "index_count": "index_count", "row_count": "row_count"}
    sort_column = sort_columns.get(sort, "size_bytes")

    where_sql = ""
    params = []
    if search:
        search_pattern = f"%{_escape_like_pattern(search)}%"
        where_sql = """
          AND (
              namespace.nspname ILIKE %s ESCAPE '!'
              OR table_class.relname ILIKE %s ESCAPE '!'
              OR (namespace.nspname || '.' || table_class.relname) ILIKE %s ESCAPE '!'
          )
        """
        params.extend([search_pattern, search_pattern, search_pattern])

    table_sizes_query = f"""
        WITH table_sizes AS (
            SELECT
                namespace.nspname AS schema_name,
                table_class.relname AS table_name,
                COALESCE(owner.rolname, '-') AS table_owner,
                pg_total_relation_size(table_class.oid)::bigint AS size_bytes,
                pg_indexes_size(table_class.oid)::bigint AS index_size_bytes,
                (
                    SELECT COUNT(*)::bigint
                    FROM pg_catalog.pg_index AS index_info
                    WHERE index_info.indrelid = table_class.oid
                ) AS index_count,
                GREATEST(table_class.reltuples::bigint, 0) AS row_count
            FROM pg_catalog.pg_class AS table_class
            JOIN pg_catalog.pg_namespace AS namespace
                ON namespace.oid = table_class.relnamespace
            LEFT JOIN pg_catalog.pg_roles AS owner
                ON owner.oid = table_class.relowner
            WHERE table_class.relkind IN ('r', 'p')
              AND namespace.nspname NOT IN ('pg_catalog', 'information_schema', 'gp_toolkit')
              AND namespace.nspname NOT LIKE 'pg_toast%%'
              {where_sql}
        )
        SELECT
            schema_name,
            table_name,
            table_owner,
            size_bytes,
            pg_size_pretty(size_bytes) AS table_size,
            index_size_bytes,
            pg_size_pretty(index_size_bytes) AS index_size,
            index_count,
            row_count,
            COUNT(*) OVER() AS total_count
        FROM table_sizes
        ORDER BY {sort_column} {direction}, schema_name ASC, table_name ASC
        LIMIT %s OFFSET %s;
    """

    table_distribution_query = f"""
        WITH table_sizes AS (
            SELECT
                namespace.nspname AS schema_name,
                table_class.relname AS table_name,
                pg_total_relation_size(table_class.oid)::bigint AS size_bytes
            FROM pg_catalog.pg_class AS table_class
            JOIN pg_catalog.pg_namespace AS namespace
                ON namespace.oid = table_class.relnamespace
            WHERE table_class.relkind IN ('r', 'p')
              AND namespace.nspname NOT IN ('pg_catalog', 'information_schema', 'gp_toolkit')
              AND namespace.nspname NOT LIKE 'pg_toast%%'
              {where_sql}
        )
        SELECT
            schema_name,
            table_name,
            size_bytes,
            pg_size_pretty(size_bytes) AS table_size
        FROM table_sizes
        ORDER BY size_bytes DESC, schema_name ASC, table_name ASC;
    """

    try:
        rows, distribution_rows = _fetch_db_resultsets(db_connection, (table_sizes_query, [*params, page_size, offset]), (table_distribution_query, params))
    except Exception as exc:
        return JsonResponse({"ok": False, "message": f"Не удалось получить размеры таблиц: {exc}"}, status=400)

    tables = [{"schema_name": row[0], "table_name": row[1], "table_owner": row[2], "size_bytes": int(row[3]), "table_size": row[4], "index_size_bytes": int(row[5]), "index_size": row[6], "index_count": int(row[7]), "row_count": int(row[8])} for row in rows]
    table_distribution = [{"schema_name": row[0], "table_name": row[1], "size_bytes": int(row[2] or 0), "table_size": row[3]} for row in distribution_rows]
    total_count = int(rows[0][9]) if rows else len(table_distribution)
    return JsonResponse({"ok": True, "tables": tables, "table_distribution": table_distribution, "page": page, "page_size": page_size, "total_count": total_count})


@require_http_methods(["POST"])
def database_views_list(request):
    payload = _read_json_body(request)
    db_connection, error_response = _require_payload_connection(request, payload)
    if error_response:
        return error_response
    page_size = 100
    page = max(int(payload.get("page") or 1), 1)
    offset = (page - 1) * page_size
    search = (payload.get("search") or "").strip()
    view_type = payload.get("view_type") or ""
    sort = payload.get("sort") or "schema_name"
    direction = "ASC" if payload.get("direction") == "asc" else "DESC"
    sort_columns = {"schema_name": "schema_name", "view_name": "view_name", "view_owner": "view_owner", "view_type": "view_type", "size_bytes": "size_bytes", "index_size_bytes": "index_size_bytes", "row_count": "row_count"}
    sort_column = sort_columns.get(sort, "schema_name")

    where_sql = ""
    params = []
    type_sql = ""
    if view_type == "ordinary":
        type_sql = "AND view_class.relkind = 'v'"
    elif view_type == "materialized":
        type_sql = "AND view_class.relkind = 'm'"
    if search:
        search_pattern = f"%{_escape_like_pattern(search)}%"
        where_sql = """
          AND (
              namespace.nspname ILIKE %s ESCAPE '!'
              OR view_class.relname ILIKE %s ESCAPE '!'
              OR owner.rolname ILIKE %s ESCAPE '!'
              OR (namespace.nspname || '.' || view_class.relname) ILIKE %s ESCAPE '!'
          )
        """
        params.extend([search_pattern, search_pattern, search_pattern, search_pattern])

    views_query = f"""
        WITH database_views AS (
            SELECT
                namespace.nspname AS schema_name,
                view_class.relname AS view_name,
                COALESCE(owner.rolname, '-') AS view_owner,
                CASE view_class.relkind
                    WHEN 'm' THEN 'Материализованное'
                    ELSE 'Обычное'
                END AS view_type,
                CASE WHEN view_class.relkind = 'm' THEN pg_total_relation_size(view_class.oid)::bigint ELSE 0::bigint END AS size_bytes,
                CASE WHEN view_class.relkind = 'm' THEN pg_indexes_size(view_class.oid)::bigint ELSE 0::bigint END AS index_size_bytes,
                CASE WHEN view_class.relkind = 'm' THEN GREATEST(view_class.reltuples::bigint, 0) ELSE 0::bigint END AS row_count
            FROM pg_catalog.pg_class AS view_class
            JOIN pg_catalog.pg_namespace AS namespace
                ON namespace.oid = view_class.relnamespace
            LEFT JOIN pg_catalog.pg_roles AS owner
                ON owner.oid = view_class.relowner
            WHERE view_class.relkind IN ('v', 'm')
              AND namespace.nspname NOT IN ('pg_catalog', 'information_schema', 'gp_toolkit')
              AND namespace.nspname NOT LIKE 'pg_toast%%'
              {type_sql}
              {where_sql}
        )
        SELECT
            schema_name,
            view_name,
            view_owner,
            view_type,
            size_bytes,
            pg_size_pretty(size_bytes) AS view_size,
            index_size_bytes,
            pg_size_pretty(index_size_bytes) AS index_size,
            row_count,
            COUNT(*) OVER() AS total_count,
            COUNT(*) FILTER (WHERE view_type = 'Материализованное') OVER() AS materialized_count,
            COUNT(*) FILTER (WHERE view_type = 'Обычное') OVER() AS ordinary_count,
            COALESCE(SUM(size_bytes) FILTER (WHERE view_type = 'Материализованное') OVER(), 0)::bigint AS materialized_size_bytes
        FROM database_views
        ORDER BY {sort_column} {direction}, schema_name ASC, view_name ASC
        LIMIT %s OFFSET %s;
    """

    try:
        rows = _fetch_db_rows(db_connection, views_query, [*params, page_size, offset])
    except Exception as exc:
        return JsonResponse({"ok": False, "message": f"Не удалось получить представления: {exc}"}, status=400)

    items = [{"schema_name": row[0], "view_name": row[1], "view_owner": row[2], "view_type": row[3], "size_bytes": int(row[4]), "view_size": row[5], "index_size_bytes": int(row[6]), "index_size": row[7], "row_count": int(row[8])} for row in rows]
    total_count = int(rows[0][9]) if rows else 0
    materialized_count = int(rows[0][10]) if rows else 0
    ordinary_count = int(rows[0][11]) if rows else 0
    materialized_size_bytes = int(rows[0][12]) if rows else 0
    summary = {"materialized_count": materialized_count, "ordinary_count": ordinary_count, "materialized_size_bytes": materialized_size_bytes, "materialized_size": _format_bytes(materialized_size_bytes)}
    return JsonResponse({"ok": True, "views": items, "summary": summary, "page": page, "page_size": page_size, "total_count": total_count})


@require_http_methods(["POST"])
def distribution_tables(request):
    payload = _read_json_body(request)
    db_connection, error_response = _require_payload_connection(request, payload)
    if error_response:
        return error_response
    tables_query = """
        SELECT
            namespace.nspname AS schema_name,
            table_class.relname AS table_name,
            CASE table_class.relkind
                WHEN 'm' THEN 'Материализованное представление'
                WHEN 'p' THEN 'Партиционированная таблица'
                ELSE 'Таблица'
            END AS object_type
        FROM pg_catalog.pg_class AS table_class
        JOIN pg_catalog.pg_namespace AS namespace
            ON namespace.oid = table_class.relnamespace
        WHERE table_class.relkind IN ('r', 'p', 'm')
          AND namespace.nspname NOT IN ('pg_catalog', 'information_schema', 'gp_toolkit')
          AND namespace.nspname NOT LIKE 'pg_toast%%'
        ORDER BY namespace.nspname ASC, table_class.relname ASC;
    """

    try:
        rows = _fetch_db_rows(db_connection, tables_query)
        tables = [{"schema_name": row[0], "table_name": row[1], "object_type": row[2]} for row in rows]
    except Exception as exc:
        return JsonResponse({"ok": False, "message": f"Не удалось получить список таблиц: {exc}"}, status=400)

    return JsonResponse({"ok": True, "tables": tables})


@require_http_methods(["POST"])
def distribution_info(request):
    payload = _read_json_body(request)
    connection_id = payload.get("id")
    schema_name = (payload.get("schema_name") or "").strip()
    table_name = (payload.get("table_name") or "").strip()
    if not connection_id:
        return JsonResponse({"ok": False, "message": "Подключение не выбрано"}, status=400)
    if not schema_name or not table_name:
        return JsonResponse({"ok": False, "message": "Таблица не выбрана"}, status=400)

    db_connection = _get_connection_for_request(request, connection_id)
    validate_query = """
        SELECT 1
        FROM pg_catalog.pg_class AS table_class
        JOIN pg_catalog.pg_namespace AS namespace
            ON namespace.oid = table_class.relnamespace
        WHERE namespace.nspname = %s
          AND table_class.relname = %s
          AND table_class.relkind IN ('r', 'p', 'm')
        LIMIT 1;
    """
    distribution_query = sql.SQL("""
        SELECT gp_segment_id::int AS segment_id, COUNT(*)::bigint AS row_count
        FROM {}.{}
        GROUP BY gp_segment_id
        ORDER BY gp_segment_id ASC;
    """).format(sql.Identifier(schema_name), sql.Identifier(table_name))

    try:
        with _open_database_connection(db_connection) as connection:
            with connection.cursor() as cursor:
                cursor.execute(validate_query, [schema_name, table_name])
                if not cursor.fetchone():
                    return JsonResponse({"ok": False, "message": "Выбранная таблица не найдена"}, status=404)
                cursor.execute(distribution_query)
                rows = cursor.fetchall()
    except Exception as exc:
        return JsonResponse({"ok": False, "message": f"Не удалось получить распределение: {exc}"}, status=400)

    segments = [{"segment_id": int(row[0]), "row_count": int(row[1])} for row in rows]
    counts = [item["row_count"] for item in segments]
    total_rows = sum(counts)
    used_segments = sum(1 for count in counts if count > 0)
    min_rows = min(counts) if counts else 0
    max_rows = max(counts) if counts else 0
    avg_rows = round(total_rows / len(counts), 2) if counts else 0
    skew_ratio = round(max_rows / min_rows, 2) if min_rows else (float(max_rows) if max_rows else 0)
    status = "высокий" if skew_ratio >= 1.5 else "средний" if skew_ratio >= 1.2 else "норм."

    return JsonResponse(
        {"ok": True, "schema_name": schema_name, "table_name": table_name, "segments": segments, "metrics": {"total_rows": total_rows, "used_segments": used_segments, "min_rows": min_rows, "max_rows": max_rows, "avg_rows": avg_rows, "skew_ratio": skew_ratio, "status": status}}
    )


@require_http_methods(["POST"])
def database_temp_table_sizes(request):
    payload = _read_json_body(request)
    db_connection, error_response = _require_payload_connection(request, payload)
    if error_response:
        return error_response
    page_size = 100
    page = max(int(payload.get("page") or 1), 1)
    offset = (page - 1) * page_size
    search = (payload.get("search") or "").strip()
    sort = payload.get("sort") or "size_bytes"
    direction = "ASC" if payload.get("direction") == "asc" else "DESC"
    sort_columns = {"schema_name": "schema_name", "table_name": "table_name", "table_owner": "table_owner", "size_bytes": "size_bytes", "session_label": "session_label"}
    sort_column = sort_columns.get(sort, "size_bytes")

    where_sql = ""
    params = []
    if search:
        search_pattern = f"%{_escape_like_pattern(search)}%"
        where_sql = """
          AND (
              namespace.nspname ILIKE %s ESCAPE '!'
              OR table_class.relname ILIKE %s ESCAPE '!'
              OR owner.rolname ILIKE %s ESCAPE '!'
              OR (namespace.nspname || '.' || table_class.relname) ILIKE %s ESCAPE '!'
          )
        """
        params.extend([search_pattern, search_pattern, search_pattern, search_pattern])

    temp_table_sizes_query = f"""
        WITH temp_table_sizes AS (
            SELECT
                namespace.nspname AS schema_name,
                table_class.relname AS table_name,
                COALESCE(owner.rolname, '-') AS table_owner,
                pg_total_relation_size(table_class.oid)::bigint AS size_bytes,
                CASE
                    WHEN namespace.nspname ~ '^pg_temp_[0-9]+$'
                    THEN 'backend ' || substring(namespace.nspname FROM '^pg_temp_([0-9]+)$')
                    ELSE '-'
                END AS session_label
            FROM pg_catalog.pg_class AS table_class
            JOIN pg_catalog.pg_namespace AS namespace
                ON namespace.oid = table_class.relnamespace
            LEFT JOIN pg_catalog.pg_roles AS owner
                ON owner.oid = table_class.relowner
            WHERE table_class.relkind IN ('r', 'p')
              AND (table_class.relpersistence = 't' OR namespace.nspname LIKE 'pg_temp_%%')
              AND namespace.nspname NOT LIKE 'pg_toast%%'
              {where_sql}
        )
        SELECT
            schema_name,
            table_name,
            table_owner,
            size_bytes,
            pg_size_pretty(size_bytes) AS table_size,
            session_label,
            COUNT(*) OVER() AS total_count
        FROM temp_table_sizes
        ORDER BY {sort_column} {direction}, schema_name ASC, table_name ASC
        LIMIT %s OFFSET %s;
    """

    temp_table_distribution_query = f"""
        WITH temp_table_sizes AS (
            SELECT
                namespace.nspname AS schema_name,
                table_class.relname AS table_name,
                pg_total_relation_size(table_class.oid)::bigint AS size_bytes
            FROM pg_catalog.pg_class AS table_class
            JOIN pg_catalog.pg_namespace AS namespace
                ON namespace.oid = table_class.relnamespace
            LEFT JOIN pg_catalog.pg_roles AS owner
                ON owner.oid = table_class.relowner
            WHERE table_class.relkind IN ('r', 'p')
              AND (table_class.relpersistence = 't' OR namespace.nspname LIKE 'pg_temp_%%')
              AND namespace.nspname NOT LIKE 'pg_toast%%'
              {where_sql}
        )
        SELECT
            schema_name,
            table_name,
            size_bytes,
            pg_size_pretty(size_bytes) AS table_size
        FROM temp_table_sizes
        ORDER BY size_bytes DESC, schema_name ASC, table_name ASC;
    """

    try:
        rows, distribution_rows = _fetch_db_resultsets(db_connection, (temp_table_sizes_query, [*params, page_size, offset]), (temp_table_distribution_query, params))
    except Exception as exc:
        return JsonResponse({"ok": False, "message": f"Не удалось получить временные таблицы: {exc}"}, status=400)

    temp_tables = [{"schema_name": row[0], "table_name": row[1], "table_owner": row[2], "size_bytes": int(row[3]), "table_size": row[4], "session_label": row[5]} for row in rows]
    temp_table_distribution = [{"schema_name": row[0], "table_name": row[1], "size_bytes": int(row[2] or 0), "table_size": row[3]} for row in distribution_rows]
    total_count = int(rows[0][6]) if rows else len(temp_table_distribution)
    return JsonResponse({"ok": True, "temp_tables": temp_tables, "temp_table_distribution": temp_table_distribution, "page": page, "page_size": page_size, "total_count": total_count})


@require_http_methods(["POST"])
def segments_info(request):
    payload = _read_json_body(request)
    db_connection, error_response = _require_payload_connection(request, payload)
    if error_response:
        return error_response
    config_query = """
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
    health_query = """
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
    metrics_query = """
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
    try:
        with _open_database_connection(db_connection) as connection:
            with connection.cursor() as cursor:
                cursor.execute(config_query)
                segments = [{"segment": row[0], "role": row[1], "preferred_role": row[2], "mode": row[3], "status": row[4], "port": row[5], "hostname": row[6], "address": row[7]} for row in cursor.fetchall()]
                cursor.execute(health_query)
                health_row = cursor.fetchone()
                cursor.execute(metrics_query)
                metrics = [{"name": row[0], "value": float(row[1])} for row in cursor.fetchall()]
    except Exception as exc:
        return JsonResponse({"ok": False, "message": f"Не удалось получить информацию о сегментах: {exc}"}, status=400)

    return JsonResponse({"ok": True, "segments": segments, "health": health_row[1] if health_row else "Нет данных", "metrics": metrics})
