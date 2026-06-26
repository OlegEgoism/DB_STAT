import json

import psycopg2
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_http_methods

from db_statistics.models import DBConnection

CONNECTION_TIMEOUT_SECONDS = 5


@ensure_csrf_cookie
def home(request):
    """Главная страница мониторинга БД."""
    return render(request, "home.html")


def cluster_status(request):
    """HTMX-фрагмент с текущим статусом кластера.

    Пока данные моковые; дальше сюда можно подключить результаты SQL-проверок
    PostgreSQL/Greenplum из раздела мониторинга работоспособности.
    """
    return render(
        request,
        "partials/_cluster_status.html",
        {"cluster_status_color": "green", "cluster_status_text": "Кластер работает"},
    )


def _connection_to_dict(connection):
    return {
        "id": str(connection.pk),
        "name": connection.name,
        "host": connection.host,
        "port": connection.port,
        "database": connection.database,
        "user": connection.username,
        "db_type": connection.db_type,
        "status": "offline",
    }


def _read_json_body(request):
    try:
        return json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return {}


def _connection_kwargs(host, port, database, username, password, ssl=True):
    return {
        "host": host,
        "port": port,
        "dbname": database,
        "user": username,
        "password": password,
        "connect_timeout": CONNECTION_TIMEOUT_SECONDS,
        "sslmode": "prefer" if ssl else "disable",
    }


def _test_connection_params(host, port, database, username, password, ssl):
    with psycopg2.connect(**_connection_kwargs(host, port, database, username, password, ssl)) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()


@require_http_methods(["GET", "POST"])
def connections(request):
    if request.method == "GET":
        items = DBConnection.objects.filter(is_active=True).order_by("name", "host")
        return JsonResponse({"connections": [_connection_to_dict(item) for item in items]})

    payload = _read_json_body(request)
    required_fields = ["name", "host", "port", "database", "user"]
    if any(not payload.get(field) for field in required_fields):
        return JsonResponse({"ok": False, "message": "Заполните все обязательные поля"}, status=400)

    defaults = {
        "username": payload["user"].strip(),
        "db_type": payload.get("db_type") or "PostgreSQL",
        "is_active": True,
    }
    if payload.get("password"):
        defaults["password"] = payload["password"]

    if payload.get("id"):
        connection = get_object_or_404(DBConnection, pk=payload["id"], is_active=True)
        connection.name = payload["name"].strip()
        connection.host = payload["host"].strip()
        connection.port = int(payload["port"])
        connection.database = payload["database"].strip()
        for field, value in defaults.items():
            setattr(connection, field, value)
        connection.save()
        return JsonResponse({"ok": True, "created": False, "connection": _connection_to_dict(connection)})

    connection, created = DBConnection.objects.update_or_create(
        name=payload["name"].strip(),
        host=payload["host"].strip(),
        port=int(payload["port"]),
        database=payload["database"].strip(),
        defaults={**defaults, "password": payload.get("password", "")},
    )
    return JsonResponse({"ok": True, "created": created, "connection": _connection_to_dict(connection)}, status=201 if created else 200)


@require_http_methods(["POST"])
def test_connection(request):
    payload = _read_json_body(request)
    connection_id = payload.get("id")

    if connection_id:
        connection = get_object_or_404(DBConnection, pk=connection_id, is_active=True)
        if all(payload.get(field) for field in ["name", "host", "port", "database", "user"]):
            params = {
                "host": payload["host"].strip(),
                "port": int(payload["port"]),
                "database": payload["database"].strip(),
                "username": payload["user"].strip(),
                "password": payload.get("password") or connection.password,
                "ssl": payload.get("ssl", True),
            }
            name = payload["name"].strip()
        else:
            params = {
                "host": connection.host,
                "port": connection.port,
                "database": connection.database,
                "username": connection.username,
                "password": connection.password,
                "ssl": payload.get("ssl", True),
            }
            name = connection.name
    else:
        required_fields = ["name", "host", "port", "database", "user"]
        if any(not payload.get(field) for field in required_fields):
            return JsonResponse({"ok": False, "message": "Заполните все обязательные поля"}, status=400)
        params = {
            "host": payload["host"].strip(),
            "port": int(payload["port"]),
            "database": payload["database"].strip(),
            "username": payload["user"].strip(),
            "password": payload.get("password", ""),
            "ssl": payload.get("ssl", True),
        }
        name = payload["name"].strip()

    try:
        _test_connection_params(**params)
    except Exception as exc:
        return JsonResponse({"ok": False, "message": f"Не удалось подключиться к {name}: {exc}"}, status=400)

    return JsonResponse({"ok": True, "message": f"Подключение к {name} успешно"})

@require_http_methods(["POST"])
def delete_connection(request):
    payload = _read_json_body(request)
    connection_id = payload.get("id")
    if not connection_id:
        return JsonResponse({"ok": False, "message": "Подключение не выбрано"}, status=400)

    connection = get_object_or_404(DBConnection, pk=connection_id, is_active=True)
    connection.is_active = False
    connection.save(update_fields=["is_active", "updated"])
    return JsonResponse({"ok": True, "message": f"Подключение {connection.name} удалено"})


@require_http_methods(["POST"])
def database_size(request):
    payload = _read_json_body(request)
    connection_id = payload.get("id")
    if not connection_id:
        return JsonResponse({"ok": False, "message": "Подключение не выбрано"}, status=400)

    db_connection = get_object_or_404(DBConnection, pk=connection_id, is_active=True)
    size_query = """
        SELECT
            pg_database_size(%s) AS size_bytes,
            pg_size_pretty(pg_database_size(%s)) AS size_pretty;
    """

    try:
        with psycopg2.connect(
            **_connection_kwargs(
                db_connection.host,
                db_connection.port,
                db_connection.database,
                db_connection.username,
                db_connection.password,
            )
        ) as connection:
            with connection.cursor() as cursor:
                cursor.execute(size_query, [db_connection.database, db_connection.database])
                size_bytes, size_pretty = cursor.fetchone()
    except Exception as exc:
        return JsonResponse({"ok": False, "message": f"Не удалось получить размер БД: {exc}"}, status=400)

    return JsonResponse(
        {
            "ok": True,
            "database": db_connection.database,
            "size_bytes": int(size_bytes),
            "size_pretty": size_pretty,
        }
    )

@require_http_methods(["POST"])
def segments_info(request):
    payload = _read_json_body(request)
    connection_id = payload.get("id")
    if not connection_id:
        return JsonResponse({"ok": False, "message": "Подключение не выбрано"}, status=400)

    db_connection = get_object_or_404(DBConnection, pk=connection_id, is_active=True)
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
        with psycopg2.connect(
            **_connection_kwargs(
                db_connection.host,
                db_connection.port,
                db_connection.database,
                db_connection.username,
                db_connection.password,
            )
        ) as connection:
            with connection.cursor() as cursor:
                cursor.execute(config_query)
                segments = [
                    {
                        "segment": row[0],
                        "role": row[1],
                        "preferred_role": row[2],
                        "mode": row[3],
                        "status": row[4],
                        "port": row[5],
                        "hostname": row[6],
                        "address": row[7],
                    }
                    for row in cursor.fetchall()
                ]
                cursor.execute(health_query)
                health_row = cursor.fetchone()
                cursor.execute(metrics_query)
                metrics = [{"name": row[0], "value": float(row[1])} for row in cursor.fetchall()]
    except Exception as exc:
        return JsonResponse({"ok": False, "message": f"Не удалось получить информацию о сегментах: {exc}"}, status=400)

    return JsonResponse({"ok": True, "segments": segments, "health": health_row[1] if health_row else "Нет данных", "metrics": metrics})

