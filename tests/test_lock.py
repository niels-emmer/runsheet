"""Tests for the advisory write lock around instance/.

The lock is a concurrency guard, not a content lock: ids.lock.json still maps
slugs to station ids. Every test here is about mutual exclusion and recovery,
never about what a write actually writes.
"""

import contextlib
import io
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

# Both invocation styles must work: `discover -s tests` puts this directory on
# sys.path, a dotted `unittest tests.test_lock` does not.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_runsheet import load_tool

runsheet = load_tool()


class LockTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)

        self._saved_instance = runsheet.INSTANCE_DIR
        runsheet.INSTANCE_DIR = self.tmp / "instance"
        self.addCleanup(lambda: setattr(runsheet, "INSTANCE_DIR", self._saved_instance))

        self.root = runsheet.INSTANCE_DIR
        self.lock_path = self.root / runsheet.WRITE_LOCK

    # -- helpers -----------------------------------------------------------
    def run_cli(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = runsheet.main(list(args))
        return code, out.getvalue() + err.getvalue()

    def seed_character(self):
        """"character init" is deliberately unlocked (it replaces the directory)."""
        code, output = self.run_cli("character", "init", "--from", "demo")
        self.assertEqual(code, 0, output)
        self.assertFalse(self.lock_path.exists(), "init writes no lock file")

    def hold_lock(self, pid, command="apply"):
        self.root.mkdir(parents=True, exist_ok=True)
        self.lock_path.write_text(json.dumps({
            "pid": pid,
            "command": command,
            "started": "2026-11-08T00:00:00Z",
            "host": socket.gethostname(),
        }) + "\n", encoding="utf-8")

    def dead_pid(self):
        child = subprocess.Popen([sys.executable, "-c", "pass"])
        child.wait()
        return child.pid


class ContentionTests(LockTestCase):
    def test_a_second_apply_fails_fast_and_names_the_holder(self):
        self.seed_character()
        self.hold_lock(os.getpid(), command="apply")

        code, output = self.run_cli("apply")

        self.assertEqual(code, 1, output)
        self.assertIn("locked by another runsheet command", output)
        self.assertIn("pid %d" % os.getpid(), output)
        self.assertIn("'apply'", output)
        self.assertTrue(self.lock_path.exists(), "a refusal must not steal the lock")

    def test_restore_takes_the_same_lock_as_apply(self):
        self.seed_character()
        self.hold_lock(os.getpid(), command="apply")

        code, output = self.run_cli("restore", str(self.tmp / "no-such-backup"))

        self.assertEqual(code, 1, output)
        self.assertIn("locked by another runsheet command", output)
        self.assertIn("'apply'", output)

    def test_a_character_write_is_blocked_too(self):
        self.seed_character()
        self.hold_lock(os.getpid(), command="apply")

        code, output = self.run_cli("character", "new-persona", "dj-blocked")

        self.assertEqual(code, 1, output)
        self.assertIn("locked by another runsheet command", output)
        self.assertFalse((self.root / "character" / "personas" / "dj-blocked.json").exists())


class ReleaseTests(LockTestCase):
    def test_the_lock_is_released_after_success(self):
        self.seed_character()

        code, output = self.run_cli("character", "new-persona", "dj-released")

        self.assertEqual(code, 0, output)
        self.assertFalse(self.lock_path.exists())

    def test_the_lock_is_released_after_failure(self):
        self.seed_character()
        # ivo-marsh exists in the demo, so the second scaffold is refused.
        code, output = self.run_cli("character", "new-persona", "ivo-marsh")

        self.assertEqual(code, 1, output)
        self.assertIn("already exists", output)
        self.assertFalse(self.lock_path.exists(), "a failed command must still release")

    def test_the_lock_file_names_the_holder_and_is_removed_on_exit(self):
        self.root.mkdir(parents=True)
        with runsheet.InstanceWriteLock(self.root, "apply"):
            self.assertTrue(self.lock_path.is_file())
            holder = json.loads(self.lock_path.read_text(encoding="utf-8"))
            self.assertEqual(holder["pid"], os.getpid())
            self.assertEqual(holder["command"], "apply")
            self.assertTrue(holder["started"])
            self.assertEqual(holder["host"], socket.gethostname())

        self.assertFalse(self.lock_path.exists())


class StaleLockTests(LockTestCase):
    def test_a_lock_from_a_dead_pid_is_recovered(self):
        self.seed_character()
        self.hold_lock(self.dead_pid(), command="apply")

        code, output = self.run_cli("character", "new-persona", "dj-recovered")

        self.assertEqual(code, 0, output)
        self.assertIn("removing stale write lock", output)
        self.assertFalse(self.lock_path.exists(), "the recovered lock is released too")

    def test_a_lock_from_another_host_is_never_stolen(self):
        # The pid cannot be checked across hosts, so the lock is treated as held.
        self.seed_character()
        self.hold_lock(self.dead_pid(), command="apply")
        holder = json.loads(self.lock_path.read_text(encoding="utf-8"))
        holder["host"] = "some-other-host"
        self.lock_path.write_text(json.dumps(holder) + "\n", encoding="utf-8")

        code, output = self.run_cli("apply")

        self.assertEqual(code, 1, output)
        self.assertIn("locked by another runsheet command", output)
        self.assertIn("some-other-host", output)


class ReadOnlyTests(LockTestCase):
    def test_validate_ignores_the_lock(self):
        self.seed_character()
        self.hold_lock(os.getpid(), command="apply")

        code, output = self.run_cli("validate")

        self.assertEqual(code, 0, output)
        self.assertTrue(self.lock_path.exists(), "a read must not release the holder's lock")


if __name__ == "__main__":
    unittest.main()
