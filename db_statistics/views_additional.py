import json

from django.conf import settings
from django.db.models import Case, CharField, F, Value, When
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone, translation
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_http_methods

from db_statistics.models import DBAudit, DBConnection, DBFavorite, DBUser
from db_statistics.view_helpers import (
    _audit_action_label,
    _audit_username,
    _available_connections,
    _available_sidebar_tabs_for_user,
    _can_manage_connections,
    _connection_audit_info,
    _connection_delete_permission_error,
    _connection_edit_permission_error,
    _connection_permission_error,
    _connection_to_dict,
    _current_db_user,
    _destructive_action_permission_error,
    _favorite_audit_info,
    _get_connection_for_request,
    _normalize_sidebar_sections,
    _normalize_sidebar_tabs,
    _read_json_body,
    _session_duration_seconds,
    _sidebar_settings_audit_info,
    _sidebar_settings_for_user,
    _sidebar_settings_values_for_user,
    _test_connection_params,
    _user_payload,
    _write_audit,
)


def page_not_found(request, exception=None):
    """Показывает фирменную страницу для неизвестных адресов."""
    return render(request, "404.html", status=404)


@ensure_csrf_cookie
def home(request):
    """Главная страница мониторинга БД."""
    db_user = _current_db_user(request)
    if not db_user:
        return redirect("login")
    return render(
        request,
        "home.html",
        {
            "db_user": db_user,
            "db_user_json": json.dumps(_user_payload(db_user), ensure_ascii=False),
            "user_can_manage_connections": db_user.role == settings.ADMIN_ROLE,
            "session_expires_at_ms": request.session.get(
                settings.SESSION_EXPIRES_AT_KEY, 0
            )
            * 1000,
        },
    )


@ensure_csrf_cookie
@require_http_methods(["GET", "POST"])
def login(request):
    """Авторизует пользователя и создаёт ограниченную по времени сессию."""
    db_user = _current_db_user(request)
    if db_user:
        return redirect("home")

    error = ""
    is_english = translation.get_language() == "en"
    login_value = ""
    email_value = ""
    session_duration_value = str(settings.DEFAULT_SESSION_DURATION_HOURS)
    if request.method == "POST":
        login_value = (request.POST.get("login") or "").strip()
        email_value = (request.POST.get("email") or "").strip()
        password_value = request.POST.get("password") or ""
        session_duration_value = (
            request.POST.get("session_duration")
            or str(settings.DEFAULT_SESSION_DURATION_HOURS)
        ).strip()
        session_duration_seconds = _session_duration_seconds(session_duration_value)

        if session_duration_seconds is None:
            if is_english:
                error = f"Session duration must be between {settings.MIN_SESSION_DURATION_MINUTES} minutes and {settings.MAX_SESSION_DURATION_HOURS} hours"
            else:
                error = f"Время сессии должно быть от {settings.MIN_SESSION_DURATION_MINUTES} минут до {settings.MAX_SESSION_DURATION_HOURS} часов"
        else:
            candidate = DBUser.objects.filter(
                login=login_value, email=email_value, is_active=True
            ).first()
            if candidate and candidate.check_password(password_value):
                db_user = candidate

        if not error and db_user:
            request.session.cycle_key()
            request.session[settings.SESSION_USER_ID_KEY] = db_user.pk
            request.session[settings.SESSION_EXPIRES_AT_KEY] = (
                int(timezone.now().timestamp()) + session_duration_seconds
            )
            request.session.set_expiry(session_duration_seconds)
            _write_audit(
                "login",
                f"Пользователь вошёл в приложение: login={db_user.login}; email={db_user.email}; role={db_user.role}; session_duration={session_duration_seconds}s",
                db_user=db_user,
            )
            return redirect("home")
        if not error:
            error = (
                "Invalid login, email or password, or the user is inactive"
                if is_english
                else "Неверный логин, почта или пароль, либо пользователь отключён"
            )

    return render(
        request,
        "login.html",
        {
            "error": error,
            "login_value": login_value,
            "email_value": email_value,
            "session_duration_value": session_duration_value,
            "min_session_duration_hours": "0.1667",
            "min_session_duration_minutes": settings.MIN_SESSION_DURATION_MINUTES,
            "max_session_duration_hours": settings.MAX_SESSION_DURATION_HOURS,
        },
    )


@require_http_methods(["POST"])
def logout(request):
    """Завершает пользовательскую сессию и записывает событие аудита."""
    db_user = _current_db_user(request)
    username = _audit_username(db_user)
    if db_user:
        audit_info = f"Пользователь вышел из приложения: login={db_user.login}; email={db_user.email}; role={db_user.role}"
    else:
        audit_info = "Выход из приложения: активный пользователь не найден"
    _write_audit("logout", audit_info, db_user=db_user, username=username)
    request.session.flush()
    return redirect("login")


@require_http_methods(["GET", "POST"])
def sidebar_settings(request):
    """Получает или сохраняет персональные настройки бокового меню."""
    db_user = _current_db_user(request)
    if not db_user:
        return JsonResponse(
            {"ok": False, "message": "Требуется вход в приложение"}, status=401
        )

    settings = _sidebar_settings_for_user(db_user)
    current_tabs, current_section_order = _sidebar_settings_values_for_user(
        settings, db_user
    )
    available_tabs = _available_sidebar_tabs_for_user(db_user)
    if request.method == "GET":
        return JsonResponse(
            {
                "ok": True,
                "available_tabs": available_tabs,
                "visible_tabs": current_tabs,
                "section_order": current_section_order,
            }
        )

    payload = _read_json_body(request)
    previous_tabs = current_tabs
    visible_tabs = _normalize_sidebar_tabs(payload.get("visible_tabs"))
    visible_tabs = [tab_id for tab_id in visible_tabs if tab_id in available_tabs]
    section_order = _normalize_sidebar_sections(payload.get("section_order"))
    settings.visible_tabs = {
        "visible_tabs": visible_tabs,
        "section_order": section_order,
    }
    settings.save(update_fields=["visible_tabs", "updated"])
    _write_audit(
        "sidebar_settings",
        _sidebar_settings_audit_info(db_user, visible_tabs, previous_tabs),
        db_user=db_user,
    )
    return JsonResponse(
        {
            "ok": True,
            "available_tabs": available_tabs,
            "visible_tabs": visible_tabs,
            "section_order": section_order,
        }
    )


@require_http_methods(["GET", "POST"])
def favorites(request):
    """Возвращает избранное пользователя или изменяет состояние одного объекта."""
    db_user = _current_db_user(request)
    if not db_user:
        return JsonResponse(
            {"ok": False, "message": "Требуется вход в приложение"}, status=401
        )

    payload = request.GET if request.method == "GET" else _read_json_body(request)
    connection_id = payload.get("id")
    if not connection_id:
        return JsonResponse(
            {"ok": False, "message": "Подключение не выбрано"}, status=400
        )
    connection = _get_connection_for_request(request, connection_id)
    queryset = DBFavorite.objects.filter(user=db_user, connection=connection)
    if request.method == "GET":
        return JsonResponse(
            {
                "ok": True,
                "favorites": [
                    {"object_type": item.object_type, "object_key": item.object_key}
                    for item in queryset
                ],
            }
        )

    object_type = str(payload.get("object_type") or "").strip()
    object_key = str(payload.get("object_key") or "").strip()
    valid_types = {value for value, _label in DBFavorite.OBJECT_TYPES}
    if object_type not in valid_types or not object_key or len(object_key) > 512:
        return JsonResponse(
            {"ok": False, "message": "Некорректный объект избранного"}, status=400
        )
    favorite, created = DBFavorite.objects.get_or_create(
        user=db_user,
        connection=connection,
        object_type=object_type,
        object_key=object_key,
    )
    if not created:
        favorite.delete()
        _write_audit(
            "favorite_remove",
            _favorite_audit_info(
                "Объект удалён из избранных объектов",
                connection,
                object_type,
                object_key,
            ),
            db_user=db_user,
        )
    else:
        _write_audit(
            "favorite_add",
            _favorite_audit_info(
                "Объект добавлен в избранные объекты",
                connection,
                object_type,
                object_key,
            ),
            db_user=db_user,
        )
    return JsonResponse(
        {
            "ok": True,
            "is_favorite": created,
            "object_type": object_type,
            "object_key": object_key,
        }
    )


@require_http_methods(["POST"])
def language_settings(request):
    """Сохраняет выбранный язык интерфейса в стандартной cookie Django."""
    payload = _read_json_body(request)
    language = str(payload.get("language", "")).lower()
    if language not in settings.SUPPORTED_LANGUAGES:
        return JsonResponse(
            {"ok": False, "message": "Поддерживаются только языки RU и EN"}, status=400
        )

    translation.activate(language)
    request.session["django_language"] = language
    response = JsonResponse({"ok": True, "language": language})
    response.set_cookie(
        settings.LANGUAGE_COOKIE_NAME,
        language,
        max_age=60 * 60 * 24 * 365,
        samesite="Lax",
    )
    return response


@require_http_methods(["GET"])
def audit_events(request):
    """Возвращает отфильтрованные события журнала аудита."""
    permission_error = _destructive_action_permission_error(request)
    if permission_error:
        return permission_error

    action_type = (request.GET.get("action_type") or "").strip()
    username = (request.GET.get("username") or "").strip()
    sort = (request.GET.get("sort") or "created").strip()
    direction = (request.GET.get("direction") or "desc").strip().lower()
    available_actions = [
        {"value": value, "label": label} for value, label in DBAudit.ACTION_TYPES
    ]
    available_sorts = {"created", "username", "action_type", "info"}
    if sort not in available_sorts or direction not in {"asc", "desc"}:
        return JsonResponse(
            {"ok": False, "message": "Некорректные параметры сортировки"}, status=400
        )

    audit_queryset = DBAudit.objects.all()
    available_users = list(
        audit_queryset.order_by("username")
        .values_list("username", flat=True)
        .distinct()
    )
    if username:
        audit_queryset = audit_queryset.filter(username=username)
    if action_type:
        valid_action_types = {value for value, _label in DBAudit.ACTION_TYPES}
        if action_type not in valid_action_types:
            return JsonResponse(
                {"ok": False, "message": "Неизвестный тип действия"}, status=400
            )
        audit_queryset = audit_queryset.filter(action_type=action_type)

    page_size = 100
    page = max(int(request.GET.get("page") or 1), 1)
    offset = (page - 1) * page_size
    order_by = sort
    if sort == "action_type":
        action_label_order = Case(
            *[
                When(action_type=value, then=Value(label))
                for value, label in DBAudit.ACTION_TYPES
            ],
            default=F("action_type"),
            output_field=CharField(),
        )
        audit_queryset = audit_queryset.annotate(action_label_order=action_label_order)
        order_by = "action_label_order"
    audit_queryset = audit_queryset.order_by(
        f"-{order_by}" if direction == "desc" else order_by, "-id"
    )
    total_count = audit_queryset.count()
    events = [
        {
            "id": audit.pk,
            "username": audit.username,
            "action_type": audit.action_type,
            "action_label": _audit_action_label(audit.action_type),
            "info": audit.info,
            "created": timezone.localtime(audit.created).strftime("%Y-%m-%d %H:%M:%S"),
        }
        for audit in audit_queryset[offset : offset + page_size]
    ]
    return JsonResponse(
        {
            "ok": True,
            "events": events,
            "actions": available_actions,
            "users": available_users,
            "page": page,
            "page_size": page_size,
            "total_count": total_count,
            "sort": sort,
            "direction": direction,
        }
    )


@require_http_methods(["GET", "POST"])
def connections(request):
    """Возвращает список или сохраняет подключение к базе данных."""
    if request.method == "GET":
        items = _available_connections(request).order_by("name", "host")
        return JsonResponse(
            {"connections": [_connection_to_dict(item) for item in items]}
        )

    if not _can_manage_connections(request):
        return _connection_permission_error()

    payload = _read_json_body(request)
    required_fields = ["name", "host", "port", "database", "user"]
    if any(not payload.get(field) for field in required_fields):
        return JsonResponse(
            {"ok": False, "message": "Заполните все обязательные поля"}, status=400
        )

    defaults = {
        "username": payload["user"].strip(),
        "db_type": payload.get("db_type") or "PostgreSQL",
        "is_active": True,
    }
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
        _write_audit(
            "connection_update",
            _connection_audit_info("Изменение подключения", connection),
            db_user=_current_db_user(request),
        )
        return JsonResponse(
            {
                "ok": True,
                "created": False,
                "connection": _connection_to_dict(connection),
            }
        )

    lookup = {
        "name": payload["name"].strip(),
        "host": payload["host"].strip(),
        "port": int(payload["port"]),
        "database": payload["database"].strip(),
        "username": defaults["username"],
    }
    existing_connection = DBConnection.objects.filter(**lookup).first()
    if (
        existing_connection
        and existing_connection.created_user_id is not None
        and (not db_user or existing_connection.created_user_id != db_user.pk)
    ):
        return _connection_edit_permission_error()

    connection, created = DBConnection.objects.update_or_create(
        defaults=defaults, **lookup
    )
    if db_user:
        if created or connection.created_user_id is None:
            connection.created_user = db_user
            connection.save(update_fields=["created_user", "updated"])
        db_user.connections.add(connection)
    _write_audit(
        "connection_create" if created else "connection_update",
        _connection_audit_info(
            "Создание подключения" if created else "Изменение подключения", connection
        ),
        db_user=db_user,
    )
    return JsonResponse(
        {"ok": True, "created": created, "connection": _connection_to_dict(connection)},
        status=201 if created else 200,
    )


@require_http_methods(["POST"])
def test_connection(request):
    """Проверяет доступность нового или сохранённого подключения."""
    payload = _read_json_body(request)
    connection_id = payload.get("id")
    has_inline_connection_data = all(
        payload.get(field) for field in ["name", "host", "port", "database", "user"]
    )
    if (
        not connection_id or has_inline_connection_data
    ) and not _can_manage_connections(request):
        return _connection_permission_error()

    if connection_id:
        connection = _get_connection_for_request(request, connection_id)
        if has_inline_connection_data:
            params = {
                "host": payload["host"].strip(),
                "port": int(payload["port"]),
                "database": payload["database"].strip(),
                "username": payload["user"].strip(),
                "password": payload.get("password") or connection.get_password(),
                "ssl": payload.get("ssl", True),
            }
            name = payload["name"].strip()
        else:
            params = {
                "host": connection.host,
                "port": connection.port,
                "database": connection.database,
                "username": connection.username,
                "password": connection.get_password(),
                "ssl": payload.get("ssl", True),
            }
            name = connection.name
    else:
        required_fields = ["name", "host", "port", "database", "user"]
        if any(not payload.get(field) for field in required_fields):
            return JsonResponse(
                {"ok": False, "message": "Заполните все обязательные поля"}, status=400
            )
        params = {
            "host": payload["host"].strip(),
            "port": int(payload["port"]),
            "database": payload["database"].strip(),
            "username": payload["user"].strip(),
            "password": payload.get("password", ""),
            "ssl": payload.get("ssl", True),
        }
        name = payload["name"].strip()

    audit_user = _current_db_user(request)
    audit_connection = connection if connection_id else None
    try:
        _test_connection_params(**params)
    except Exception as exc:
        if audit_connection:
            info = _connection_audit_info(
                "Проверка подключения", audit_connection, result="Ошибка", error=exc
            )
        else:
            info = (
                f"Действие: Проверка нового подключения; Подключение: {name}; "
                f"Хост: {params['host']}; Порт: {params['port']}; База данных: {params['database']}; "
                f"Пользователь БД: {params['username']}; Результат: Ошибка; Ошибка: {exc}"
            )
        _write_audit("connection_test", info, db_user=audit_user)
        return JsonResponse(
            {"ok": False, "message": f"Не удалось подключиться к {name}: {exc}"},
            status=400,
        )

    if audit_connection:
        info = _connection_audit_info(
            "Проверка подключения", audit_connection, result="Успешно"
        )
    else:
        info = (
            f"Действие: Проверка нового подключения; Подключение: {name}; "
            f"Хост: {params['host']}; Порт: {params['port']}; База данных: {params['database']}; "
            f"Пользователь БД: {params['username']}; Результат: Успешно"
        )
    _write_audit("connection_test", info, db_user=audit_user)
    return JsonResponse({"ok": True, "message": f"Подключение к {name} успешно"})


@require_http_methods(["POST"])
def delete_connection(request):
    """Удаляет сохранённое подключение пользователя."""
    if not _can_manage_connections(request):
        return _connection_permission_error()

    payload = _read_json_body(request)
    connection_id = payload.get("id")
    if not connection_id:
        return JsonResponse(
            {"ok": False, "message": "Подключение не выбрано"}, status=400
        )

    connection = _get_connection_for_request(request, connection_id)
    db_user = _current_db_user(request)
    if not db_user or connection.created_user_id != db_user.pk:
        return _connection_delete_permission_error()

    audit_info = _connection_audit_info("Удаление подключения", connection)
    connection.is_active = False
    connection.save(update_fields=["is_active", "updated"])
    _write_audit("connection_delete", audit_info, db_user=db_user)
    return JsonResponse(
        {"ok": True, "message": f"Подключение {connection.name} удалено"}
    )
