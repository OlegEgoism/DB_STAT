"""Session/login state, per-request permission checks, and rate limiting.

Split out of views/helpers.py (see its module docstring).
"""

from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.core.cache import cache
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone

from db_statistics.models import DBConnection, DBUser


def _current_db_user(request):
    """Возвращает активного пользователя приложения из текущей сессии"""
    if _session_has_expired(request.session):
        request.session.flush()
        return None
    user_id = request.session.get(settings.SESSION_USER_ID_KEY)
    if not user_id:
        return None
    try:
        return DBUser.objects.get(pk=user_id, is_active=True)
    except DBUser.DoesNotExist:
        request.session.pop(settings.SESSION_USER_ID_KEY, None)
        return None


def _session_duration_seconds(value):
    """Преобразует длительность сессии из часов в секунды"""
    try:
        seconds = int(Decimal(str(value)) * 60 * 60)
    except (InvalidOperation, TypeError, ValueError):
        return None
    if not settings.MIN_SESSION_DURATION_SECONDS <= seconds <= settings.MAX_SESSION_DURATION_SECONDS:
        return None
    return seconds


def _session_has_expired(session, now_timestamp=None):
    """Проверяет, истёк ли срок действия пользовательской сессии"""
    expires_at = session.get(settings.SESSION_EXPIRES_AT_KEY)
    if not expires_at:
        return False
    try:
        expires_at = int(expires_at)
    except (TypeError, ValueError):
        return True
    current_timestamp = int(timezone.now().timestamp()) if now_timestamp is None else int(now_timestamp)
    return expires_at <= current_timestamp


def _can_manage_connections(request):
    """Проверяет право пользователя управлять подключениями"""
    db_user = _current_db_user(request)
    return bool(db_user and db_user.role == settings.ADMIN_ROLE)


def _destructive_action_permission_error(request):
    """Проверяет право пользователя выполнять разрушающие операции"""
    db_user = _current_db_user(request)
    if not db_user:
        return JsonResponse({"ok": False, "message": "Требуется вход в приложение"}, status=401)
    if db_user.role != settings.ADMIN_ROLE:
        return JsonResponse({"ok": False, "message": "Действие доступно только Администратору"}, status=403)
    return None


def _connection_permission_error():
    """Возвращает ошибку недостаточных прав на управление подключениями"""
    return JsonResponse({"ok": False, "message": "Создавать и редактировать подключения может только Администратор"}, status=403)


def _connection_delete_permission_error():
    """Возвращает ошибку недостаточных прав на удаление подключения"""
    return JsonResponse({"ok": False, "message": "Удалять подключение может только его создатель"}, status=403)


def _connection_edit_permission_error():
    """Возвращает ошибку недостаточных прав на изменение подключения"""
    return JsonResponse({"ok": False, "message": "Редактировать подключение может только его создатель"}, status=403)


def _rate_limit_exceeded(key, limit, window_seconds):
    """Ограничение частоты на основе кэша: не более `limit` вызовов за `window_seconds` для данного ключа.

    Не претендует на точное скользящее окно — только защита от скрипта или
    скомпрометированной сессии, забрасывающей конкретное действие (тест
    подключения, VACUUM FULL) подряд идущими запросами.
    """
    cache.add(key, 0, timeout=window_seconds)
    try:
        current = cache.incr(key)
    except ValueError:
        cache.set(key, 1, timeout=window_seconds)
        current = 1
    return current > limit


def _rate_limit_response(action_description):
    """Единый ответ 429 для всех ограничений частоты."""
    return JsonResponse({"ok": False, "message": f"Слишком много запросов: {action_description}. Повторите позже."}, status=429)


def _available_connections(request):
    """Возвращает доступные текущему пользователю подключения"""
    db_user = _current_db_user(request)
    if not db_user:
        return DBConnection.objects.none()
    return db_user.connections.filter(is_active=True).select_related("created_user")


def _get_connection_for_request(request, connection_id):
    """Получает доступное пользователю подключение по идентификатору"""
    return get_object_or_404(_available_connections(request), pk=connection_id)


def _require_payload_connection(request, payload):
    """Проверяет запрос и возвращает выбранное подключение."""
    connection_id = payload.get("id")
    if not connection_id:
        return None, JsonResponse({"ok": False, "message": "Подключение не выбрано"}, status=400)
    return _get_connection_for_request(request, connection_id), None


def _greenplum_only_error():
    """Возвращает ошибку для функций распределённых СУБД."""
    return JsonResponse({"ok": False, "message": "Эта функция доступна только для подключений типа Greenplum или Greengage"}, status=400)


def _require_greenplum_connection(request, payload):
    """Возвращает подключение Greenplum или совместимого с ним Greengage."""
    db_connection, error_response = _require_payload_connection(request, payload)
    if error_response:
        return None, error_response
    if not db_connection.is_greenplum_compatible:
        return None, _greenplum_only_error()
    return db_connection, None
