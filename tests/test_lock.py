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

    def test_a_skills_write_is_blocked_too(self):
        self.seed_character()
        self.hold_lock(os.getpid(), command="apply")

        code, output = self.run_cli("skills", "new", "dj-blocked")

        self.assertEqual(code, 1, output)
        self.assertIn("locked by another runsheet command", output)
        self.assertFalse((self.root / "skills" / "dj-blocked").exists())

    def test_mock_commands_take_the_lock_too(self):
        # --mock changes the station, not the checkout: a mock apply still races
        # on instance/ with a live command, so it must contend on the same lock.
        self.seed_character()
        self.hold_lock(os.getpid(), command="apply")

        code, output = self.run_cli("--mock", "apply", "--yes")

        self.assertEqual(code, 1, output)
        self.assertIn("locked by another runsheet command", output)

    def test_pull_force_fails_fast_while_a_lock_is_held(self):
        self.seed_character()
        self.hold_lock(os.getpid(), command="apply")

        code, output = self.run_cli("pull", "--force")

        self.assertEqual(code, 1, output)
        self.assertIn("locked by another runsheet command", output)
        self.assertTrue((self.root / "ids.lock.json").is_file(),
                        "the holder's instance/ must be untouched")

    def test_character_init_force_fails_fast_while_a_lock_is_held(self):
        self.seed_character()
        before = sorted(path.name for path in (self.root / "character" / "personas").glob("*.json"))
        self.hold_lock(os.getpid(), command="apply")

        code, output = self.run_cli("character", "init", "--force", "--from", "demo")

        self.assertEqual(code, 1, output)
        self.assertIn("locked by another runsheet command", output)
        after = sorted(path.name for path in (self.root / "character" / "personas").glob("*.json"))
        self.assertEqual(after, before, "a refused replace must not delete the holder's files")


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

    def test_replacing_instance_contents_keeps_the_write_lock(self):
        # `pull --force` and `character init --force` empty instance/ rather
        # than removing it, so the lock survives the swap it protects.
        self.root.mkdir(parents=True)
        (self.root / "ids.lock.json").write_text("{}", encoding="utf-8")
        (self.root / "character").mkdir()
        (self.root / "character" / "character.json").write_text("{}", encoding="utf-8")

        with runsheet.InstanceWriteLock(self.root, "pull"):
            runsheet.replace_instance_dir(self.root)

            self.assertTrue(self.lock_path.is_file(), "the lock must survive the replace")
            self.assertFalse((self.root / "ids.lock.json").exists())
            self.assertFalse((self.root / "character").exists())

        self.assertFalse(self.lock_path.exists())

    def test_character_init_force_releases_after_replacing(self):
        self.seed_character()

        code, output = self.run_cli("character", "init", "--force", "--from", "demo")

        self.assertEqual(code, 0, output)
        self.assertFalse(self.lock_path.exists(), "the swap must release the lock")


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

    def test_an_unreadable_lock_is_reported_not_removed(self):
        self.seed_character()
        self.lock_path.write_text("not a lock\n", encoding="utf-8")

        code, output = self.run_cli("apply")

        self.assertEqual(code, 1, output)
        self.assertIn("locked by another runsheet command", output)
        self.assertIn("unreadable lock file", output)
        self.assertTrue(self.lock_path.exists(), "the unreadable lock must not be stolen")
        self.assertEqual(self.lock_path.read_text(encoding="utf-8"), "not a lock\n")

    def test_a_delayed_breaker_cannot_steal_a_replacement_lock(self):
        # Reproduces the two-breaker race: B samples a dead holder, A removes it
        # and installs its own live lock, then B reaches the break step. The
        # breaker must make B re-read and refuse rather than unlink A's lock.
        self.seed_character()
        self.hold_lock(os.getpid(), command="apply")
        stale_snapshot = {
            "pid": self.dead_pid(),
            "command": "apply",
            "started": "2026-11-08T00:00:00Z",
            "host": socket.gethostname(),
        }

        real_read = runsheet._read_write_lock
        calls = {"count": 0}

        def delayed_read(path):
            calls["count"] += 1
            if calls["count"] == 1:
                return dict(stale_snapshot)  # the snapshot taken before A replaced it
            return real_read(path)

        saved = runsheet._read_write_lock
        runsheet._read_write_lock = delayed_read
        self.addCleanup(lambda: setattr(runsheet, "_read_write_lock", saved))

        with self.assertRaises(runsheet.ToolError) as caught:
            runsheet.InstanceWriteLock(self.root, "apply").acquire()

        self.assertIn("locked by another runsheet command", str(caught.exception))
        self.assertTrue(self.lock_path.exists(), "the live replacement lock must survive")
        self.assertEqual(json.loads(self.lock_path.read_text())["pid"], os.getpid())
        self.assertFalse((self.root / runsheet.WRITE_LOCK_BREAK).exists(),
                         "the breaker is removed even when it does not break the lock")

    def test_a_breaker_left_by_a_crash_refuses_rather_than_stealing(self):
        self.seed_character()
        self.hold_lock(self.dead_pid(), command="apply")
        (self.root / runsheet.WRITE_LOCK_BREAK).write_text(json.dumps({
            "pid": os.getpid(),
            "command": "apply breaker",
            "started": "2026-11-08T00:00:00Z",
            "host": socket.gethostname(),
        }) + "\n", encoding="utf-8")

        code, output = self.run_cli("apply")

        self.assertEqual(code, 1, output)
        self.assertIn("stale-lock breaker", output)
        self.assertTrue(self.lock_path.exists(), "a breaker must not license a steal")


class ReadOnlyTests(LockTestCase):
    def test_validate_ignores_the_lock(self):
        self.seed_character()
        self.hold_lock(os.getpid(), command="apply")

        code, output = self.run_cli("validate")

        self.assertEqual(code, 0, output)
        self.assertTrue(self.lock_path.exists(), "a read must not release the holder's lock")


if __name__ == "__main__":
    unittest.main()
