"""Файловые блокировки фоновых задач: признак того, что задачу ещё выполняет живой процесс.

Статус «Выполняется» в базе не говорит, жив ли процесс, который её выполняет: если
воркер погиб по SIGKILL, задача навсегда остаётся в этом статусе. Поэтому процесс,
выполняющий задачу, держит на её lock-файле эксклюзивную блокировку. Операционная
система снимает блокировку при любой смерти процесса, поэтому свободная блокировка
означает, что владельца уже нет. Колонки в базе для этого не нужны.
"""

import errno
import functools
import os
import tempfile
import time
from contextlib import contextmanager

if os.name == "nt":
    import msvcrt
else:
    import fcntl

LOCK_DIR = os.path.join(tempfile.gettempdir(), "db-stat-job-locks")


def _lock_path(job_id):
    return os.path.join(LOCK_DIR, f"{job_id}.lock")


@contextmanager
def _open_lock(job_id):
    os.makedirs(LOCK_DIR, exist_ok=True)
    handle = open(_lock_path(job_id), "a+b")
    try:
        # Byte-range locks on Windows may extend past EOF, so an empty file is
        # sufficient. Never truncate, write or delete it while others use it.
        yield handle
    finally:
        handle.close()


def _acquire_lock(handle, *, blocking):
    if os.name != "nt":
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB))
        except BlockingIOError:
            return False
        return True

    # LK_LOCK gives up after ten attempts; retry LK_NBLCK ourselves to preserve
    # flock's indefinite blocking behavior. Every handle must lock the same byte.
    while True:
        handle.seek(0)
        try:
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as exc:
            if exc.errno not in {errno.EACCES, errno.EAGAIN, errno.EDEADLK}:
                raise
            if not blocking:
                return False
            time.sleep(0.05)
        else:
            return True


def _release_lock(handle):
    if os.name == "nt":
        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
    else:
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def with_job_lock(function):
    """Декоратор: держит блокировку задачи на время выполнения функции (первый аргумент — id задачи).

    Блокировка берётся до захвата задачи в базе, поэтому sweep в другом процессе
    не примет задачу за осиротевшую в промежутке между захватом и стартом.
    """

    @functools.wraps(function)
    def wrapper(job_id, *args, **kwargs):
        with _open_lock(job_id) as handle:
            _acquire_lock(handle, blocking=True)
            try:
                return function(job_id, *args, **kwargs)
            finally:
                _release_lock(handle)

    return wrapper


def job_owner_alive(job_id):
    """True, если блокировку задачи держит живой процесс; False — владельца нет."""
    with _open_lock(job_id) as handle:
        if not _acquire_lock(handle, blocking=False):
            return True
        _release_lock(handle)
        return False
