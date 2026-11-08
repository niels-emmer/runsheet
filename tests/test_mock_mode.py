"""`--mock`: the real CLI, pointed at tests/mock_station.py in this process.

Every test here goes through `runsheet.main(argv)`, so the flag is exercised the
way a person or an agent uses it - argparse included - rather than by calling the
mock library directly. No test contacts a station, ssh, or the network.
"""

import contextlib
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_runsheet import load_tool

runsheet = load_tool()

# An address that cannot be reached and a host that cannot be ssh'd. If --mock
# ever consulted the real configuration, a status call would try one of them.
LIVE_ENV = {
    "SUBWAVE_BASE_URL": "http://127.0.0.1:1",
    "SUBWAVE_ADMIN_USER": "live-admin",
    "SUBWAVE_ADMIN_PASS": "live-pass",
    "SUBWAVE_HOST": "not-a-real-host.invalid",
    "SUBWAVE_STATE_DIR": "/var/sub-wave",
    "SUBWAVE_CONTAINER": "live-controller",
    "SUBWAVE_STATION_PASSWORD": "live-station",
}


class MockModeTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)

        self._saved_instance = runsheet.INSTANCE_DIR
        runsheet.INSTANCE_DIR = self.tmp / "instance"
        self.addCleanup(lambda: setattr(runsheet, "INSTANCE_DIR", self._saved_instance))

        # Record every station `main` starts, so a test can read back what the
        # mock actually stored (stop() only closes the socket and removes the dir).
        self.servers = []
        self.module = runsheet._load_mock_station()
        self._real_start_mock = self.module.start_mock

        def recording(*args, **kwargs):
            server = self._real_start_mock(*args, **kwargs)
            self.servers.append(server)
            return server

        self.module.start_mock = recording
        self.addCleanup(lambda: setattr(self.module, "start_mock", self._real_start_mock))

    def run_cli(self, *argv, environ=None):
        saved = {}
        if environ:
            for key, value in environ.items():
                saved[key] = os.environ.get(key)
                os.environ[key] = value
        out, err = io.StringIO(), io.StringIO()
        try:
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                code = runsheet.main(list(argv))
        finally:
            for key, value in saved.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
        return code, out.getvalue(), err.getvalue()


class StatusRoutingTests(MockModeTestCase):
    def test_status_talks_to_the_mock_and_ignores_the_real_env(self):
        code, out, err = self.run_cli("--mock", "status", environ=LIVE_ENV)
        self.assertEqual(code, 0, out + err)
        self.assertIn("mock      http://127.0.0.1:", out)
        self.assertIn("endpoint  http://127.0.0.1:", out)
        self.assertIn("tier      2 - host access", out)
        self.assertIn("station   Harbour Lights", out)
        for value in LIVE_ENV.values():
            self.assertNotIn(value, out, "--mock consulted the real environment")
        self.assertNotIn("not-a-real-host.invalid", err)

    def test_the_flag_is_accepted_after_the_command_too(self):
        code, out, err = self.run_cli("status", "--mock", environ=LIVE_ENV)
        self.assertEqual(code, 0, out + err)
        self.assertIn("mock      http://127.0.0.1:", out)

    def test_mock_mode_never_reads_the_dotenv_file(self):
        # Config() only calls load_dotenv on the non-mock path; make that visible.
        with mock.patch.object(runsheet, "load_dotenv",
                               side_effect=AssertionError(".env was consulted")):
            code, out, err = self.run_cli("--mock", "status", environ=LIVE_ENV)
        self.assertEqual(code, 0, out + err)
        self.assertIn("station   Harbour Lights", out)

    def test_without_the_flag_the_real_configuration_is_used(self):
        # Hermetic: a developer's own SUBWAVE_HOST must not make this probe ssh.
        environ = {"SUBWAVE_BASE_URL": "http://127.0.0.1:1"}
        real_config = runsheet.Config
        with mock.patch.object(runsheet, "Config",
                               lambda *a, **kw: real_config(dotenv={}, environ=environ)):
            code, out, err = self.run_cli("status")
        self.assertNotIn("mock      ", out)
        self.assertIn("endpoint  http://127.0.0.1:1", out)


class PullAndDiffTests(MockModeTestCase):
    def test_pull_then_diff_are_routed_through_the_mock(self):
        code, out, err = self.run_cli("--mock", "pull", "--force", environ=LIVE_ENV)
        self.assertEqual(code, 0, out + err)
        self.assertIn("wrote     instance/", out)
        self.assertTrue((runsheet.INSTANCE_DIR / "ids.lock.json").is_file())
        # a tier-2 capture, not the trimmed tier-1 one
        lock = json.loads((runsheet.INSTANCE_DIR / "ids.lock.json").read_text())
        self.assertEqual(lock["capture"]["tier"], 2)
        self.assertFalse(lock["capture"]["lossy"])

        code, out, err = self.run_cli("--mock", "diff", environ=LIVE_ENV)
        self.assertEqual(code, 0, out + err)
        self.assertIn("result    in sync", out)


class ApplyRoundTripTests(MockModeTestCase):
    def test_apply_yes_writes_then_reads_back_and_verifies(self):
        code, out, err = self.run_cli("--mock", "pull", "--force")
        self.assertEqual(code, 0, out + err)

        personas = sorted((runsheet.INSTANCE_DIR / "character" / "personas").glob("*.json"))
        self.assertTrue(personas, "pull captured no personas")
        document = json.loads(personas[0].read_text())
        document["name"] = "Renamed By Mock Apply"
        personas[0].write_text(json.dumps(document, indent=2))

        code, out, err = self.run_cli(
            "--mock", "apply", "--yes", "--force-now",
            "--backup-dir", str(self.tmp / "backups"), environ=LIVE_ENV)
        self.assertEqual(code, 0, out + err)
        self.assertIn("result    5 step(s) written; ids.lock.json updated", out)
        self.assertIn("wrote     POST /api/settings", out)

        lock = json.loads((runsheet.INSTANCE_DIR / "ids.lock.json").read_text())
        self.assertTrue(lock["applied"]["verified"],
                        "tier-2 read-back did not prove the write landed")

        station = self.servers[1].station  # servers[0] was pull's
        stored = {persona["id"]: persona for persona in station.settings["personas"]}
        self.assertEqual(stored[document["id"]]["name"], "Renamed By Mock Apply")
        sent = {(request["method"], request["path"])
                for request in station.requests if request["authorised"]}
        self.assertIn(("POST", "/api/settings"), sent)
        self.assertIn(("PUT", "/api/schedule"), sent)
        self.assertTrue((self.tmp / "backups").is_dir(), "apply took no pre-write backup")


class LifecycleTests(MockModeTestCase):
    def test_the_real_transports_are_back_after_each_command(self):
        real_ssh_run, real_ssh_probe = runsheet.ssh_run, runsheet.ssh_probe
        code, out, err = self.run_cli("--mock", "status")
        self.assertEqual(code, 0, out + err)
        self.assertIs(runsheet.ssh_run, real_ssh_run)
        self.assertIs(runsheet.ssh_probe, real_ssh_probe)

    def test_a_missing_mock_module_is_a_config_error_not_a_traceback(self):
        saved = runsheet._MOCK_MODULE
        runsheet._MOCK_MODULE = None
        self.addCleanup(lambda: setattr(runsheet, "_MOCK_MODULE", saved))
        with mock.patch.object(runsheet, "REPO_ROOT", self.tmp), \
                mock.patch.object(runsheet, "_MOCK_MODULE", None):
            code, out, err = self.run_cli("--mock", "status")
        self.assertEqual(code, runsheet.EXIT_CONFIG)
        self.assertIn("--mock needs", err)
        self.assertNotIn("Traceback", err)


if __name__ == "__main__":
    unittest.main()
