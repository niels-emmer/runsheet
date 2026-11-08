"""`capabilities` answers "can this verb succeed right now?" without trying it.

The contract is AGENTS.md's tier table: tier 1 is portable and lossy, so backup,
restore and `apply --prune` are refused and pull/diff/apply are degraded; tier 2
has host access and everything is available. Tier detection is stubbed, so these
tests touch no ssh and no network - and a test asserts that the command attempts
no operation at all.
"""

import contextlib
import io
import json
import unittest
from types import SimpleNamespace

from test_runsheet import load_tool

runsheet = load_tool()


class CapabilitiesTestCase(unittest.TestCase):
    def setUp(self):
        self._saved_detect = runsheet.detect_tier
        self.addCleanup(lambda: setattr(runsheet, "detect_tier", self._saved_detect))
        self.config = runsheet.Config(dotenv={}, environ={})

    def report(self, tier, as_json=False):
        runsheet.detect_tier = lambda config, probe=None: (tier, "mock tier %d" % tier)
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code = runsheet.cmd_capabilities(
                self.config, SimpleNamespace(json=as_json))
        self.assertEqual(code, runsheet.EXIT_OK)
        return buffer.getvalue()

    # -- tier 1 -------------------------------------------------------------

    def test_tier_1_backup_is_refused(self):
        caps = json.loads(self.report(1, as_json=True))["capabilities"]
        self.assertFalse(caps["backup"]["available"])
        self.assertIn("schedule.json", caps["backup"]["reason"])
        self.assertIn("host access", caps["backup"]["reason"])

    def test_tier_1_restore_is_refused(self):
        caps = json.loads(self.report(1, as_json=True))["capabilities"]
        self.assertFalse(caps["restore"]["available"])
        self.assertIn("schedule.json", caps["restore"]["reason"])

    def test_tier_1_prune_needs_host_access(self):
        caps = json.loads(self.report(1, as_json=True))["capabilities"]
        self.assertFalse(caps["apply --prune"]["available"])
        self.assertIn("host access", caps["apply --prune"]["reason"])

    def test_tier_1_pull_is_available_but_lossy(self):
        caps = json.loads(self.report(1, as_json=True))["capabilities"]
        self.assertTrue(caps["pull"]["available"])
        self.assertIn("lossy", caps["pull"]["note"])
        self.assertIn("--allow-lossy", caps["pull"]["note"])

    def test_tier_1_apply_says_no_backup_is_required(self):
        caps = json.loads(self.report(1, as_json=True))["capabilities"]
        self.assertTrue(caps["apply"]["available"])
        self.assertIn("--no-backup", caps["apply"]["note"])

    def test_tier_1_local_verbs_are_available(self):
        caps = json.loads(self.report(1, as_json=True))["capabilities"]
        for verb in ("character", "skills", "blocklist", "onair"):
            with self.subTest(verb=verb):
                self.assertTrue(caps[verb]["available"])
                self.assertNotIn("reason", caps[verb])

    # -- tier 2 -------------------------------------------------------------

    def test_tier_2_every_verb_is_available(self):
        caps = json.loads(self.report(2, as_json=True))["capabilities"]
        self.assertEqual(set(caps), set(runsheet.CAPABILITY_VERBS))
        for verb, entry in caps.items():
            with self.subTest(verb=verb):
                self.assertTrue(entry["available"])
                self.assertNotIn("reason", entry)

    # -- --json -------------------------------------------------------------

    def test_json_has_the_documented_shape(self):
        payload = json.loads(self.report(1, as_json=True))
        self.assertEqual(payload["tier"], 1)
        self.assertIsInstance(payload["capabilities"], dict)
        self.assertEqual(set(payload["capabilities"]), set(runsheet.CAPABILITY_VERBS))
        for verb, entry in payload["capabilities"].items():
            with self.subTest(verb=verb):
                self.assertIsInstance(entry["available"], bool)
                if not entry["available"]:
                    self.assertTrue(entry["reason"])

    def test_json_tier_2_is_clean(self):
        payload = json.loads(self.report(2, as_json=True))
        self.assertEqual(payload["tier"], 2)
        self.assertTrue(payload["capabilities"]["backup"]["available"])
        self.assertTrue(payload["capabilities"]["apply --prune"]["available"])

    # -- text and read-only -------------------------------------------------

    def test_text_output_names_the_tier_and_each_verdict(self):
        output = self.report(1)
        self.assertIn("tier      1", output)
        for verb in runsheet.CAPABILITY_VERBS:
            self.assertIn(verb, output)
        backup_line = next(line for line in output.splitlines()
                           if line.startswith("backup"))
        self.assertIn("no", backup_line)

    def test_it_attempts_no_operation(self):
        def explode(*args, **kwargs):
            raise AssertionError("`capabilities` must not talk to the station")

        saved = (runsheet.ssh_run, runsheet.http_json, runsheet.take_backup)
        runsheet.ssh_run = runsheet.http_json = runsheet.take_backup = explode
        self.addCleanup(lambda: (setattr(runsheet, "ssh_run", saved[0]),
                                 setattr(runsheet, "http_json", saved[1]),
                                 setattr(runsheet, "take_backup", saved[2])))
        self.report(1)
        self.report(2)

    def test_real_cli_defaults_to_tier_1_json(self):
        # No host access configured: detection stops before any ssh probe.
        saved = runsheet.Config
        runsheet.Config = lambda *a, **k: saved(dotenv={}, environ={})
        self.addCleanup(lambda: setattr(runsheet, "Config", saved))
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code = runsheet.main(["capabilities", "--json"])
        self.assertEqual(code, runsheet.EXIT_OK)
        payload = json.loads(buffer.getvalue())
        self.assertEqual(payload["tier"], 1)
        self.assertIn("capabilities", payload)


if __name__ == "__main__":
    unittest.main()
