"""Файловые блокировки фоновых задач: признак того, что задачу ещё выполняет живой процесс.

Статус «Выполняется» в базе не говорит, жив ли процесс, который её выполняет: если
воркер погиб по SIGKILL, задача навсегда остаётся в этом статусе. Поэтому процесс,
выполняющий задачу, держит на её lock-файле эксклюзивную блокировку flock. Операционная
система снимает блокировку при любой смерти процесса, поэтому свободная блокировка
означает, что владельца уже нет. Колонки в базе для этого не нужны.
"""

import fcntl
import functools
import os
import tempfile
from contextlib import contextmanager

LOCK_DIR = os.path.join(tempfile.gettempdir(), "db-stat-job-locks")


def _lock_path(job_id):
    return os.path.join(LOCK_DIR, f"{job_id}.lock")


@contextmanager
def _open_lock(job_id):
    os.makedirs(LOCK_DIR, exist_ok=True)
    handle = open(_lock_path(job_id), "a+")
    try:
        yield handle
    finally:
        handle.close()


def with_job_lock(function):
    """Декоратор: держит блокировку задачи на время выполнения функции (первый аргумент — id задачи).

    Блокировка берётся до захвата задачи в базе, поэтому sweep в другом процессе
    не примет задачу за осиротевшую в промежутке между захватом и стартом.
    """

    @functools.wraps(function)
    def wrapper(job_id, *args, **kwargs):
        with _open_lock(job_id) as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                return function(job_id, *args, **kwargs)
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    return wrapper


def job_owner_alive(job_id):
    """True, если блокировку задачи держит живой процесс; False — владельца нет."""
    with _open_lock(job_id) as handle:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return True
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        return False
