import subprocess
import sys
import tempfile
import threading
import uuid
from pathlib import Path
from unittest import TestCase, mock

from db_statistics import job_locks
from db_statistics.job_locks import job_owner_alive, with_job_lock


class JobLockTests(TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory(prefix="dbstat-test-")
        self.addCleanup(directory.cleanup)
        patch = mock.patch.object(job_locks, "LOCK_DIR", directory.name)
        patch.start()
        self.addCleanup(patch.stop)

    def _start_owner(self, job_id, *, wait_until_locked=True):
        script = """
import sys
from db_statistics import job_locks
job_locks.LOCK_DIR = sys.argv[1]
@job_locks.with_job_lock
def run(job_id):
    print("locked", flush=True)
    sys.stdin.readline()
run(sys.argv[2])
"""
        process = subprocess.Popen([sys.executable, "-c", script, job_locks.LOCK_DIR, str(job_id)], cwd=Path(__file__).resolve().parents[2], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        def cleanup():
            if process.poll() is None:
                process.kill()
            process.communicate(timeout=10)

        self.addCleanup(cleanup)
        if not wait_until_locked:
            return process
        # communicate(timeout=...) below bounds completion; this read is bounded
        # by a timer so a broken lock implementation cannot hang the test suite.
        timer = threading.Timer(10, process.kill)
        timer.start()
        try:
            self.assertEqual(process.stdout.readline().strip(), "locked")
        finally:
            timer.cancel()
        return process

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

    def test_other_process_holds_lock_until_normal_exit(self):
        job_id = uuid.uuid4()
        process = self._start_owner(job_id)
        self.assertTrue(job_owner_alive(job_id))
        self.assertFalse(job_owner_alive(uuid.uuid4()), "другая задача не должна блокироваться")
        process.communicate(input="done\n", timeout=10)
        self.assertEqual(process.returncode, 0)
        self.assertFalse(job_owner_alive(job_id))

    def test_lock_is_released_when_owner_is_killed(self):
        job_id = uuid.uuid4()
        process = self._start_owner(job_id)
        self.assertTrue(job_owner_alive(job_id))
        process.kill()
        process.communicate(timeout=10)
        self.assertFalse(job_owner_alive(job_id))

    def test_second_worker_waits_for_same_job(self):
        job_id = uuid.uuid4()
        owner = self._start_owner(job_id)
        waiter = self._start_owner(job_id, wait_until_locked=False)
        with self.assertRaises(subprocess.TimeoutExpired):
            waiter.communicate(timeout=0.3)
        owner.communicate(input="done\n", timeout=10)
        stdout, stderr = waiter.communicate(timeout=10)
        self.assertEqual(waiter.returncode, 0, stderr)
        self.assertEqual(stdout.strip(), "locked")
        self.assertFalse(job_owner_alive(job_id))

    def test_unexpected_lock_errors_are_not_treated_as_live_owner(self):
        with mock.patch.object(job_locks, "_acquire_lock", side_effect=OSError("disk failure")):
            with self.assertRaises(OSError):
                job_owner_alive(uuid.uuid4())
