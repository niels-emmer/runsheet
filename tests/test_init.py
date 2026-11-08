"""`init`: one command from a bare ssh host (or HTTP credentials) to a working .env.

The manual flow was copy .env.example, set SUBWAVE_HOST, run status, read two
printed lines, paste them back, run status again. These tests pin the one-step
replacement: discovery is the same `discover_state_dirs` status uses, `ssh_run`
is stubbed, and the assertions are on the file init actually writes and the
confirmation it prints afterwards.
"""

import contextlib
import io
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from test_runsheet import load_tool

runsheet = load_tool()

EXAMPLE = runsheet.REPO_ROOT / ".env.example"


class FakeResult:
    def __init__(self, stdout="", stderr="", returncode=0):
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode


class InitTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)

        self._saved_root = runsheet.REPO_ROOT
        self._saved_instance = runsheet.INSTANCE_DIR
        runsheet.REPO_ROOT = self.tmp
        runsheet.INSTANCE_DIR = self.tmp / "instance"
        self.addCleanup(lambda: setattr(runsheet, "REPO_ROOT", self._saved_root))
        self.addCleanup(lambda: setattr(runsheet, "INSTANCE_DIR", self._saved_instance))

        self._saved_ssh_run = runsheet.ssh_run
        self.addCleanup(lambda: setattr(runsheet, "ssh_run", self._saved_ssh_run))

        self._saved_environ = dict(os.environ)
        self.addCleanup(self._restore_environ)
        for key in runsheet.Config.KEYS:
            os.environ.pop(key, None)

    def _restore_environ(self):
        os.environ.clear()
        os.environ.update(self._saved_environ)

    # -- helpers -----------------------------------------------------------
    def env_path(self):
        return self.tmp / ".env"

    def copy_example(self):
        if EXAMPLE.is_file():
            shutil.copy2(EXAMPLE, self.tmp / ".env.example")

    def write_env(self, text):
        self.env_path().write_text(text, encoding="utf-8")

    def read_env(self):
        return runsheet.load_dotenv(self.env_path())

    def run_cli(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                code = runsheet.main(list(args))
            except SystemExit as exc:
                code = exc.code
        return code, out.getvalue() + err.getvalue()

    def stub_ssh(self, *results):
        """Queue ssh results; the last repeats. A plain string means stdout, rc 0."""
        queue = [r if isinstance(r, FakeResult) else FakeResult(stdout=r) for r in results]
        calls = []

        def fake(config, command, **kwargs):
            calls.append((command, config))
            return queue[min(len(calls) - 1, len(queue) - 1)]

        runsheet.ssh_run = fake
        return calls


class Tier2InitTests(InitTestCase):
    def test_host_discovery_writes_all_three_lines_and_confirms_tier_2(self):
        self.copy_example()
        calls = self.stub_ssh("FOUND sub-wave-controller /var/sub-wave\n", FakeResult())

        code, output = self.run_cli("init", "--host", "me@host")

        self.assertEqual(code, 0, output)
        values = self.read_env()
        self.assertEqual(values["SUBWAVE_HOST"], "me@host")
        self.assertEqual(values["SUBWAVE_CONTAINER"], "sub-wave-controller")
        self.assertEqual(values["SUBWAVE_STATE_DIR"], "/var/sub-wave")
        self.assertIn("SUBWAVE_HOST=me@host", output)
        self.assertIn("SUBWAVE_STATE_DIR=/var/sub-wave", output)
        self.assertIn("tier      2 - host access", output)
        self.assertIn("SUBWAVE_BASE_URL is not set", output,
                      "tier 2 without the HTTP side must say what is still missing")
        self.assertEqual(len(calls), 2, "one discovery call, then one tier-2 probe")
        self.assertEqual(calls[0][1].host, "me@host")
        self.assertIn("docker ps", calls[0][0])

    def test_host_with_http_flags_writes_all_of_them(self):
        # Tier 2 is HTTP *plus* host access: --host alone is not a full setup.
        self.copy_example()
        self.stub_ssh("FOUND sub-wave-controller /var/sub-wave\n", FakeResult())

        code, output = self.run_cli(
            "init", "--host", "me@host",
            "--base-url", "http://127.0.0.1:7700/",
            "--admin-user", "admin", "--admin-pass", "fake-admin-pass")

        self.assertEqual(code, 0, output)
        values = self.read_env()
        self.assertEqual(values["SUBWAVE_HOST"], "me@host")
        self.assertEqual(values["SUBWAVE_CONTAINER"], "sub-wave-controller")
        self.assertEqual(values["SUBWAVE_STATE_DIR"], "/var/sub-wave")
        self.assertEqual(values["SUBWAVE_BASE_URL"], "http://127.0.0.1:7700",
                         "the normalised URL must be the one written")
        self.assertEqual(values["SUBWAVE_ADMIN_USER"], "admin")
        self.assertEqual(values["SUBWAVE_ADMIN_PASS"], "fake-admin-pass")
        self.assertNotIn("next      SUBWAVE_BASE_URL", output)

    def test_host_with_a_malformed_base_url_is_refused_before_discovery(self):
        self.copy_example()

        def refuse(*a, **kw):
            raise AssertionError("a malformed --base-url must be rejected before ssh")

        runsheet.ssh_run = refuse
        code, output = self.run_cli("init", "--host", "me@host",
                                    "--base-url", "station.lan:7700")

        self.assertEqual(code, 2)
        self.assertIn("must start with http:// or https://", output)
        self.assertFalse(self.env_path().exists())

    def test_mock_mode_is_refused_because_there_is_no_env_to_write(self):
        args = SimpleNamespace(host=None, base_url="http://127.0.0.1:7700",
                               admin_user=None, admin_pass=None,
                               station_password=None, force=False, mock=True)
        config = runsheet.Config(dotenv={}, environ={})

        with self.assertRaises(runsheet.ToolError) as caught:
            runsheet.cmd_init(config, args)

        self.assertIn("has no .env to write", str(caught.exception))
        self.assertFalse(self.env_path().exists())

    def test_no_env_yet_starts_from_the_example_so_comments_survive(self):
        self.copy_example()
        self.stub_ssh("FOUND sub-wave-controller /var/sub-wave\n", FakeResult())

        code, output = self.run_cli("init", "--host", "me@host")

        self.assertEqual(code, 0, output)
        text = self.env_path().read_text(encoding="utf-8")
        self.assertIn("# Copy to .env and fill in", text)
        self.assertIn("SUBWAVE_HOST=me@host", text)

    def test_the_env_file_is_owner_only(self):
        self.copy_example()
        self.stub_ssh("FOUND sub-wave-controller /var/sub-wave\n", FakeResult())

        self.run_cli("init", "--host", "me@host")

        self.assertEqual(self.env_path().stat().st_mode & 0o777, 0o600)

    def test_an_unreachable_host_writes_nothing(self):
        self.copy_example()
        self.stub_ssh(FakeResult("", "ssh: connect to host port 22: refused", 255))

        code, output = self.run_cli("init", "--host", "me@host")

        self.assertEqual(code, 1)
        self.assertFalse(self.env_path().exists(), "a failed discovery must not write .env")
        self.assertIn("no container on me@host has a mounted settings.json", output)
        self.assertIn("connect to host", output)


class Tier1InitTests(InitTestCase):
    def test_flags_are_written_in_one_step(self):
        self.copy_example()

        code, output = self.run_cli(
            "init", "--base-url", "http://127.0.0.1:7700",
            "--admin-user", "admin", "--admin-pass", "fake-admin-pass",
            "--station-password", "fake-listener-pass")

        self.assertEqual(code, 0, output)
        values = self.read_env()
        self.assertEqual(values["SUBWAVE_BASE_URL"], "http://127.0.0.1:7700")
        self.assertEqual(values["SUBWAVE_ADMIN_USER"], "admin")
        self.assertEqual(values["SUBWAVE_ADMIN_PASS"], "fake-admin-pass")
        self.assertEqual(values["SUBWAVE_STATION_PASSWORD"], "fake-listener-pass")
        self.assertEqual(values["SUBWAVE_HOST"], "", "tier 1 writes no host")
        self.assertIn("tier      1 - HTTP only", output)
        self.assertIn("endpoint  http://127.0.0.1:7700", output)

    def test_the_admin_password_is_never_echoed(self):
        self.copy_example()

        code, output = self.run_cli(
            "init", "--base-url", "http://127.0.0.1:7700",
            "--admin-pass", "fake-admin-pass")

        self.assertEqual(code, 0, output)
        self.assertNotIn("fake-admin-pass", output)
        self.assertIn("SUBWAVE_ADMIN_PASS=***", output)

    def test_without_a_host_or_base_url_it_explains_the_two_choices(self):
        self.copy_example()

        code, output = self.run_cli("init")

        self.assertEqual(code, 2)
        self.assertIn("--host", output)
        self.assertIn("--base-url", output)
        self.assertFalse(self.env_path().exists())

    def test_a_named_credentials_file_is_the_one_written(self):
        # RUNSHEET_ENV_FILE replaces ./.env for Config, so init must write there
        # or it would create a file the tool never reads.
        shared = self.tmp / "shared.env"
        shared.write_text("SUBWAVE_ADMIN_USER=admin\n", encoding="utf-8")
        os.environ["RUNSHEET_ENV_FILE"] = str(shared)

        code, output = self.run_cli("init", "--base-url", "http://127.0.0.1:7700",
                                    "--admin-pass", "fake-admin-pass")

        self.assertEqual(code, 0, output)
        values = runsheet.load_dotenv(shared)
        self.assertEqual(values["SUBWAVE_BASE_URL"], "http://127.0.0.1:7700")
        self.assertEqual(values["SUBWAVE_ADMIN_PASS"], "fake-admin-pass")
        self.assertFalse(self.env_path().exists(),
                         "init must not create a .env the tool never reads")


class ClobberTests(InitTestCase):
    def test_a_populated_env_is_refused_without_force_and_left_untouched(self):
        self.copy_example()
        original = "SUBWAVE_BASE_URL=http://old:7700\nSUBWAVE_ADMIN_PASS=fake-old-pass\n"
        self.write_env(original)

        code, output = self.run_cli("init", "--base-url", "http://new:7700")

        self.assertEqual(code, 1)
        self.assertEqual(self.env_path().read_text(encoding="utf-8"), original)
        self.assertIn("would write", output)
        self.assertIn("SUBWAVE_BASE_URL=http://new:7700", output)
        self.assertIn("--force", output)

    def test_force_updates_the_named_keys_and_keeps_the_others(self):
        self.copy_example()
        self.write_env("SUBWAVE_BASE_URL=http://old:7700\nSUBWAVE_ADMIN_PASS=fake-old-pass\n")

        code, output = self.run_cli("init", "--base-url", "http://new:7700", "--force")

        self.assertEqual(code, 0, output)
        values = self.read_env()
        self.assertEqual(values["SUBWAVE_BASE_URL"], "http://new:7700")
        self.assertEqual(values["SUBWAVE_ADMIN_PASS"], "fake-old-pass",
                         "a key init did not name must survive")

    def test_duplicate_keys_are_all_rewritten_so_the_last_one_matches(self):
        # The manual route leaves empty template lines and appends pasted ones at
        # the bottom. load_dotenv keeps the last, so rewriting only the first
        # occurrence used to report a write that had no effect.
        self.copy_example()
        self.write_env("SUBWAVE_STATE_DIR=\n"
                       "SUBWAVE_CONTAINER=\n"
                       "SUBWAVE_HOST=me@host\n"
                       "SUBWAVE_CONTAINER=old-container\n"
                       "SUBWAVE_STATE_DIR=/old/state\n")
        self.stub_ssh("FOUND sub-wave-controller /var/sub-wave\n", FakeResult())

        code, output = self.run_cli("init", "--host", "new@host", "--force")

        self.assertEqual(code, 0, output)
        values = self.read_env()
        self.assertEqual(values["SUBWAVE_HOST"], "new@host")
        self.assertEqual(values["SUBWAVE_CONTAINER"], "sub-wave-controller")
        self.assertEqual(values["SUBWAVE_STATE_DIR"], "/var/sub-wave")
        self.assertEqual(
            self.env_path().read_text(encoding="utf-8").count("/old/state"), 0,
            "the stale duplicate must be rewritten, not left to win")

    def test_an_empty_env_is_not_treated_as_populated(self):
        self.copy_example()  # every key present, every value empty

        code, output = self.run_cli("init", "--base-url", "http://127.0.0.1:7700")

        self.assertEqual(code, 0, output)


if __name__ == "__main__":
    unittest.main()
