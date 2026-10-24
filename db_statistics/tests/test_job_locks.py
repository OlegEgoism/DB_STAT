import os
import uuid
from unittest import mock

from django.test import SimpleTestCase

from db_statistics import job_locks
from db_statistics.job_locks import job_owner_alive, with_job_lock


class JobLockTests(SimpleTestCase):
    def setUp(self):
        self._tmp = mock.patch.object(job_locks, "LOCK_DIR", os.path.join(os.environ.get("TMPDIR", "/tmp"), f"dbstat-test-{uuid.uuid4().hex}"))
        self._tmp.start()

    def tearDown(self):
        self._tmp.stop()

    def test_job_without_lock_file_is_orphaned(self):
        self.assertFalse(job_owner_alive(uuid.uuid4()))

    def test_running_job_holds_lock_and_is_alive(self):
        job_id = uuid.uuid4()
        seen = {}

        @with_job_lock
        def run(job):
            # Проверка из того же процесса другим дескриптором: блокировка уже занята владельцем.
            seen["alive_during_run"] = job_owner_alive(job)

        run(job_id)

        self.assertTrue(seen["alive_during_run"])
        self.assertFalse(job_owner_alive(job_id), "после завершения блокировка должна освободиться")

    def test_lock_is_released_when_function_raises(self):
        job_id = uuid.uuid4()

        @with_job_lock
        def failing(job):
            raise RuntimeError("boom")

        with self.assertRaises(RuntimeError):
            failing(job_id)

        self.assertFalse(job_owner_alive(job_id))
