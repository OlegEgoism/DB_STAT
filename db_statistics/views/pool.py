"""Target-database connection handling: parameter building, pooling, and query execution.

Split out of views/helpers.py (see its module docstring) because this is the
most self-contained, concurrency-sensitive piece — it has no dependency on
auth/session/audit concerns, only on settings and psycopg2.
"""

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
    """Формирует параметры подключения psycopg2."""
    return {"host": _normalize_database_host(host), "port": port, "dbname": database, "user": username, "password": password, "connect_timeout": settings.CONNECTION_TIMEOUT_SECONDS, "sslmode": "prefer" if ssl else "disable"}


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
    return (db_connection.pk, db_connection.host, db_connection.port, db_connection.database, db_connection.username, db_connection.get_password(), ssl)


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


@contextmanager
def _open_database_connection(db_connection, ssl=True):
    """Берёт соединение с сохранённой базой данных из пула этого подключения.

    Соединение возвращается в пул при выходе из блока `with` вместо того,
    чтобы закрывать сокет и открывать новый на каждый запрос — это особенно
    важно для часто опрашиваемых панелей (активные запросы/сессии/блокировки).
    Если соединение осталось в аварийном состоянии (ошибка внутри блока) или
    оказалось нежизнеспособным, оно закрывается и не возвращается в пул, чтобы
    следующий запрос получил заведомо рабочее соединение.
    """
    pool = _get_connection_pool(db_connection, ssl)
    connection = pool.getconn()
    discard = False
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
                    connection.autocommit = False
                else:
                    connection.rollback()
            except psycopg2.Error:
                discard = True
        pool.putconn(connection, close=discard)


def _fetch_db_rows(db_connection, query, params=None):
    """Выполняет запрос и возвращает все строки результата."""
    with _open_database_connection(db_connection) as connection:
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
        return None, JsonResponse({"ok": False, "message": _safe_db_error_message(action_description, exc)}, status=400)
