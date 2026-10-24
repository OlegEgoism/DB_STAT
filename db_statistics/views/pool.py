"""Target-database connection handling: parameter building, pooling, and query execution.

Split out of views/helpers.py (see its module docstring) because this is the
most self-contained, concurrency-sensitive piece — it has no dependency on
auth/session/audit concerns, only on settings and psycopg2.
"""

import hashlib
import logging
import threading
from contextlib import closing, contextmanager

import psycopg2
from django.conf import settings
from django.http import JsonResponse
from psycopg2.pool import ThreadedConnectionPool

logger = logging.getLogger(__name__)


def _normalize_database_host(host):
    """Нормализует имя хоста базы данных для локальных подключений"""
    normalized_host = (host or "").strip().lower()
    if normalized_host in settings.LOCALHOST_NAMES:
        return settings.LOCALHOST_DB_HOST
    return host


def _connection_kwargs(host, port, database, username, password, ssl=True):
    """Формирует параметры подключения psycopg2.

    Таймауты передаются в самом подключении, поэтому действуют на все запросы
    пула, а не только на отдельные view. См. комментарий к DB_LOCK_TIMEOUT_MS.
    """
    options = f"-c lock_timeout={settings.DB_LOCK_TIMEOUT_MS} -c statement_timeout={settings.DB_STATEMENT_TIMEOUT_MS}"
    return {"host": _normalize_database_host(host), "port": port, "dbname": database, "user": username, "password": password, "connect_timeout": settings.CONNECTION_TIMEOUT_SECONDS, "sslmode": "prefer" if ssl else "disable", "options": options}


def _test_connection_params(host, port, database, username, password, ssl):
    """Проверяет подключение по переданным параметрам."""
    with closing(psycopg2.connect(**_connection_kwargs(host, port, database, username, password, ssl))) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()


_connection_pools = {}
_connection_pools_lock = threading.Lock()


def _pool_key(db_connection, ssl):
    """Ключ пула: слепок текущих параметров подключения.

    Если пользователь меняет хост/пользователя/пароль сохранённого
    подключения, ключ меняется вместе с ними, и код ниже сам закрывает пул со
    старыми параметрами — новые соединения не создаются с устаревшим паролем.
    """
    # В ключе хранится отпечаток пароля, а не сам пароль: ключи пулов видны в отладке и дампах памяти.
    password_fingerprint = hashlib.sha256(db_connection.get_password().encode("utf-8")).hexdigest()
    return (db_connection.pk, db_connection.host, db_connection.port, db_connection.database, db_connection.username, password_fingerprint, ssl, settings.DB_LOCK_TIMEOUT_MS, settings.DB_STATEMENT_TIMEOUT_MS)


def _get_connection_pool(db_connection, ssl):
    """Возвращает пул psycopg2-соединений для этого подключения, создавая его при необходимости."""
    key = _pool_key(db_connection, ssl)
    with _connection_pools_lock:
        pool = _connection_pools.get(key)
        if pool is not None:
            return pool
        for stale_key in [existing for existing in _connection_pools if existing[0] == db_connection.pk]:
            _connection_pools.pop(stale_key).closeall()
        pool = ThreadedConnectionPool(settings.DB_CONNECTION_POOL_MIN_CONN, settings.DB_CONNECTION_POOL_MAX_CONN, **_connection_kwargs(db_connection.host, db_connection.port, db_connection.database, db_connection.username, db_connection.get_password(), ssl))
        _connection_pools[key] = pool
        return pool


def _close_connection_pools_for(connection_id):
    """Закрывает и забывает все пулы соединений для указанного подключения (например, при удалении)."""
    with _connection_pools_lock:
        for stale_key in [existing for existing in _connection_pools if existing[0] == connection_id]:
            _connection_pools.pop(stale_key).closeall()


def _apply_session_timeouts(connection, statement_ms, lock_ms):
    """Задаёт таймауты сессии и фиксирует их, не трогая открытую транзакцию вызывающего кода.

    SET откатывается вместе с транзакцией, поэтому значение фиксируется коммитом;
    вызывается только на чистом соединении из пула.
    """
    with connection.cursor() as cursor:
        cursor.execute(f"SET statement_timeout = {int(statement_ms)}")
        cursor.execute(f"SET lock_timeout = {int(lock_ms)}")
    if not connection.autocommit:
        connection.commit()


def _restore_session_timeouts(connection):
    """Возвращает таймауты сессии к значениям из параметров подключения перед отдачей в пул."""
    with connection.cursor() as cursor:
        cursor.execute("RESET statement_timeout")
        cursor.execute("RESET lock_timeout")


@contextmanager
def _open_database_connection(db_connection, ssl=True, background=False):
    """Берёт соединение с сохранённой базой данных из пула этого подключения.

    Соединение возвращается в пул при выходе из блока `with` вместо того,
    чтобы закрывать сокет и открывать новый на каждый запрос — это особенно
    важно для часто опрашиваемых панелей (активные запросы/сессии/блокировки).
    Если соединение осталось в аварийном состоянии (ошибка внутри блока) или
    оказалось нежизнеспособным, оно закрывается и не возвращается в пул, чтобы
    следующий запрос получил заведомо рабочее соединение.

    background=True для фоновых задач (VACUUM, PDF): им выставляются более
    длинный statement_timeout и отдельный lock_timeout, а после выхода таймауты
    возвращаются к обычным значениям, чтобы пул не сохранил их для других запросов.
    """
    pool = _get_connection_pool(db_connection, ssl)
    connection = pool.getconn()
    discard = False
    if background:
        try:
            _apply_session_timeouts(connection, settings.DB_BACKGROUND_STATEMENT_TIMEOUT_MS, settings.DB_BACKGROUND_LOCK_TIMEOUT_MS)
        except psycopg2.Error:
            pool.putconn(connection, close=True)
            raise
    try:
        yield connection
    except Exception:
        discard = True
        raise
    finally:
        if connection.closed:
            discard = True
        elif not discard:
            try:
                if connection.autocommit:
                    if background:
                        _restore_session_timeouts(connection)
                    connection.autocommit = False
                else:
                    connection.rollback()
                    if background:
                        _restore_session_timeouts(connection)
                        connection.commit()
            except psycopg2.Error:
                discard = True
        pool.putconn(connection, close=discard)


def _fetch_db_rows(db_connection, query, params=None, background=False):
    """Выполняет запрос и возвращает все строки результата."""
    with _open_database_connection(db_connection, background=background) as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, params or [])
            return cursor.fetchall()


def _fetch_db_row(db_connection, query, params=None):
    """Выполняет запрос и возвращает первую строку результата."""
    with _open_database_connection(db_connection) as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, params or [])
            return cursor.fetchone()


def _fetch_db_resultsets(db_connection, *queries):
    """Выполняет несколько запросов в одном соединении."""
    resultsets = []
    with _open_database_connection(db_connection) as connection:
        with connection.cursor() as cursor:
            for query, params in queries:
                cursor.execute(query, params or [])
                resultsets.append(cursor.fetchall())
    return resultsets


def _safe_db_error_message(action_description, exc):
    """Логирует подробности ошибки БД и возвращает безопасное сообщение для клиента.

    Сырой текст исключения psycopg2/драйвера может содержать имена схем, таблиц
    и другие внутренние детали целевой БД, которые не должны попадать в ответ
    пользователю (в том числе Аналитику с ограниченным доступом).
    """
    logger.warning("%s", action_description, exc_info=exc)
    return f"{action_description}. Подробности см. в журнале сервера приложения"


def _query_or_error(action_description, fn):
    """Выполняет запрос к целевой БД, превращая ошибки драйвера в безопасный JSON-ответ.

    Перехватывает только ``psycopg2.Error`` — ошибки самой целевой БД (сеть,
    авторизация, синтаксис SQL и т.п.). Программные ошибки (KeyError, TypeError
    и другие баги в обработке результата) не перехватываются и всплывают как
    обычно, а не маскируются под «ошибку базы данных».

    Возвращает (результат fn(), None) при успехе или (None, JsonResponse) при
    ошибке БД — вызывающий код должен вернуть этот JsonResponse клиенту.
    """
    try:
        return fn(), None
    except psycopg2.Error as exc:
        return None, _db_error_response(action_description, exc)


# Коды SQLSTATE, которые означают не ошибку запроса, а перегрузку или блокировку.
LOCK_NOT_AVAILABLE_SQLSTATE = "55P03"
QUERY_CANCELED_SQLSTATE = "57014"
LOCKED_MESSAGE = "Объект заблокирован другой транзакцией: посмотрите вкладку «Блокировки»"
TIMEOUT_MESSAGE = "Запрос не уложился в допустимое время: попробуйте позже или сузьте фильтр"


def _db_error_response(action_description, exc):
    """Ответ для ошибки БД: блокировка и таймаут — 503 с понятной причиной, остальное — 400."""
    sqlstate = getattr(exc, "pgcode", None)
    if sqlstate in (LOCK_NOT_AVAILABLE_SQLSTATE, QUERY_CANCELED_SQLSTATE):
        reason = LOCKED_MESSAGE if sqlstate == LOCK_NOT_AVAILABLE_SQLSTATE else TIMEOUT_MESSAGE
        logger.info("%s: SQLSTATE %s", action_description, sqlstate)
        return JsonResponse({"ok": False, "message": f"{action_description}. {reason}"}, status=503)
    return JsonResponse({"ok": False, "message": _safe_db_error_message(action_description, exc)}, status=400)
