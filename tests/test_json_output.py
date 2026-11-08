"""`status`, `diff` and `validate` take --json for programmatic callers.

The formatted text is the human view; these tests pin the machine view, so an
agent can decide "is this diff safe to apply?" without parsing prose.
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

sys.path.insert(0, str(Path(__file__).resolve().parent))

import mock_station
from test_runsheet import load_tool

runsheet = load_tool()
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "station.json"


def run_cli(*args):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = runsheet.main(list(args))
        except SystemExit as exc:
            code = exc.code
    return code, out.getvalue(), err.getvalue()


def run_json(*args):
    code, output, err = run_cli(*args)
    return code, json.loads(output), err


class StatusJsonTests(unittest.TestCase):
    """Tier 1 with a stub station: no ssh, no instance, no network."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)

        self._saved = (runsheet.INSTANCE_DIR, runsheet.detect_tier, runsheet.http_json)
        runsheet.INSTANCE_DIR = self.tmp / "instance"
        runsheet.detect_tier = lambda config, probe=None: (1, "missing SUBWAVE_HOST")
        runsheet.http_json = lambda *a, **kw: (200, {
            "activeShow": {"name": "Late Harbour", "persona": {"name": "Ada Vance"}},
            "nowPlaying": {"title": "A Track", "artist": "An Artist"},
            "listeners": {"current": 7, "peak": 12},
            "streamOnline": True,
        })
        self.addCleanup(self._restore)

        self._saved_environ = dict(os.environ)
        self.addCleanup(self._restore_environ)
        for key in ("SUBWAVE_HOST", "SUBWAVE_STATE_DIR", "SUBWAVE_CONTAINER"):
            os.environ.pop(key, None)
        os.environ["SUBWAVE_BASE_URL"] = "http://127.0.0.1:7700"

    def _restore(self):
        runsheet.INSTANCE_DIR, runsheet.detect_tier, runsheet.http_json = self._saved

    def _restore_environ(self):
        os.environ.clear()
        os.environ.update(self._saved_environ)

    def test_status_json_has_tier_air_and_sync(self):
        code, document, err = run_json("status", "--json")
        self.assertEqual(code, 0, err)
        self.assertEqual(document["command"], "status")
        self.assertTrue(document["ok"])
        payload = document["payload"]
        self.assertEqual(payload["tier"], 1)
        self.assertEqual(payload["endpoint"], "http://127.0.0.1:7700")
        self.assertIsNone(payload["apiError"])
        self.assertEqual(payload["onAir"]["show"], "Late Harbour")
        self.assertEqual(payload["onAir"]["persona"], "Ada Vance")
        self.assertEqual(payload["onAir"]["track"]["title"], "A Track")
        self.assertEqual(payload["onAir"]["listeners"], {"current": 7, "peak": 12})
        self.assertTrue(payload["onAir"]["streamOnline"])
        self.assertEqual(payload["reads"], "trimmed")
        self.assertEqual(payload["backup"], "refused")
        self.assertEqual(payload["sync"]["state"], "no-instance")

    def test_a_failed_station_call_sets_ok_false(self):
        runsheet.http_json = lambda *a, **kw: (503, {})
        code, document, _ = run_json("status", "--json")
        self.assertNotEqual(code, 0)
        self.assertFalse(document["ok"])
        self.assertIn("503", document["payload"]["apiError"])
        self.assertIsNone(document["payload"]["onAir"])


class StatusSyncJsonTests(unittest.TestCase):
    """Tier 2: the sync field must say in-sync, then drifted, without prose."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        document = json.loads(FIXTURE.read_text(encoding="utf-8"))
        self.settings, self.schedule = document["settings"], document["schedule"]

        self._saved = (runsheet.INSTANCE_DIR, runsheet.detect_tier,
                       runsheet.read_state_file, runsheet.http_json)
        runsheet.INSTANCE_DIR = self.tmp / "instance"
        runsheet.detect_tier = lambda config, probe=None: (2, "mock")
        runsheet.read_state_file = lambda config, name: json.dumps(
            self.settings if name == "settings.json" else self.schedule)
        runsheet.http_json = lambda *a, **kw: (200, {
            "activeShow": None, "nowPlaying": {}, "listeners": {}, "streamOnline": False})
        self.addCleanup(self._restore)

        self._saved_environ = dict(os.environ)
        self.addCleanup(self._restore_environ)
        os.environ["SUBWAVE_BASE_URL"] = "http://127.0.0.1:7700"

        model = runsheet.build_live_model(self.settings, self.schedule)
        runsheet.write_instance(model, {}, capture={
            "tier": 2, "at": "2026-10-31T00:00:00Z", "lossy": False, "lost": []})

    def _restore(self):
        (runsheet.INSTANCE_DIR, runsheet.detect_tier,
         runsheet.read_state_file, runsheet.http_json) = self._saved

    def _restore_environ(self):
        os.environ.clear()
        os.environ.update(self._saved_environ)

    def test_an_untouched_capture_is_in_sync(self):
        code, document, err = run_json("status", "--json")
        self.assertEqual(code, 0, err)
        payload = document["payload"]
        self.assertEqual(payload["tier"], 2)
        self.assertEqual(payload["sync"], {"state": "in-sync", "changes": 0,
                                           "detail": "in sync with instance/"})
        self.assertEqual(payload["reads"], "full")
        self.assertEqual(payload["backup"], "complete")
        self.assertGreater(payload["config"]["personas"], 0)
        self.assertGreater(payload["config"]["gridCells"], 0)

    def test_a_changed_file_shows_as_drift(self):
        path = sorted((runsheet.INSTANCE_DIR / "character" / "personas").glob("*.json"))[0]
        persona = json.loads(path.read_text(encoding="utf-8"))
        persona["warmth"] = 10 if persona.get("warmth") != 10 else 1
        path.write_text(json.dumps(persona, indent=2), encoding="utf-8")

        code, document, err = run_json("status", "--json")
        self.assertEqual(code, 0, err)
        sync = document["payload"]["sync"]
        self.assertEqual(sync["state"], "drifted")
        self.assertGreaterEqual(sync["changes"], 1)
        self.assertIn("diff", sync["detail"])


class DiffJsonTests(unittest.TestCase):
    def setUp(self):
        self.server = mock_station.start_mock()
        self.addCleanup(self.server.stop)
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)

        self._saved_environ = dict(os.environ)
        self.addCleanup(self._restore_environ)
        for key in ("SUBWAVE_HOST", "SUBWAVE_STATE_DIR"):
            os.environ.pop(key, None)
        os.environ.update({
            "SUBWAVE_BASE_URL": self.server.url,
            "SUBWAVE_ADMIN_USER": "mock-admin",
            "SUBWAVE_ADMIN_PASS": "mock-pass",
        })

        self._saved = (runsheet.INSTANCE_DIR, runsheet.SshStateSource,
                       runsheet.read_state_file, runsheet.detect_tier,
                       runsheet.builtin_skill_slugs)
        runsheet.INSTANCE_DIR = self.tmp / "instance"
        runsheet.SshStateSource = lambda config: runsheet.LocalStateSource(
            self.server.state_dir)
        runsheet.read_state_file = lambda config, name: json.dumps(
            self.server.station.settings if name == "settings.json"
            else self.server.station.schedule)
        runsheet.detect_tier = lambda config, probe=None: (2, "mock")
        runsheet.builtin_skill_slugs = lambda config, state: {"curiosity"}
        self.addCleanup(self._restore)

        document = json.loads(FIXTURE.read_text(encoding="utf-8"))
        model = runsheet.build_live_model(document["settings"], document["schedule"])
        runsheet.write_instance(model, {}, capture={
            "tier": 2, "at": "2026-10-31T00:00:00Z", "lossy": False, "lost": []})
        blocklist = json.loads(json.dumps(self.server.station.blocklist))
        runsheet.assign_rule_slugs(blocklist["rules"], {})
        runsheet.write_json(runsheet.INSTANCE_DIR / runsheet.BLOCKLIST_FILE, blocklist)
        lock = {"version": 1, "rules": {}, "ids": {}}
        for rule in blocklist["rules"]:
            if rule.get("id"):
                lock["rules"][rule["slug"]] = rule["id"]
                lock["ids"][rule["id"]] = rule["slug"]
        runsheet.write_json(runsheet.INSTANCE_DIR / runsheet.BLOCKLIST_LOCK, lock)

    def _restore(self):
        (runsheet.INSTANCE_DIR, runsheet.SshStateSource, runsheet.read_state_file,
         runsheet.detect_tier, runsheet.builtin_skill_slugs) = self._saved

    def _restore_environ(self):
        os.environ.clear()
        os.environ.update(self._saved_environ)

    def pull(self):
        code, _, err = run_cli("pull", "--force")
        self.assertEqual(code, 0, err)

    def test_a_clean_capture_has_no_differences(self):
        self.pull()
        code, document, err = run_json("diff", "--json")
        self.assertEqual(code, 0, err)
        self.assertEqual(document["command"], "diff")
        self.assertTrue(document["ok"])
        payload = document["payload"]
        self.assertEqual(payload["count"], 0)
        self.assertFalse(payload["trimmed"])
        for kind in ("personas", "shows"):
            for label in ("added", "removed", "changed"):
                self.assertEqual(payload["changes"][kind][label], [], "%s.%s" % (kind, label))
        self.assertEqual(payload["changes"]["grid"]["changedDays"], [])
        self.assertEqual(payload["changes"]["settings"]["changed"], [])
        self.assertTrue(payload["changes"]["override"]["unchanged"])

    def test_a_changed_host_is_reported_by_slug(self):
        self.pull()
        path = sorted((runsheet.INSTANCE_DIR / "character" / "personas").glob("*.json"))[0]
        persona = json.loads(path.read_text(encoding="utf-8"))
        persona["warmth"] = 10 if persona.get("warmth") != 10 else 1
        path.write_text(json.dumps(persona, indent=2), encoding="utf-8")

        code, document, err = run_json("diff", "--json")
        self.assertEqual(code, 1, err)
        self.assertFalse(document["ok"])
        payload = document["payload"]
        self.assertGreaterEqual(payload["count"], 1)
        self.assertIn(persona["id"], payload["changes"]["personas"]["changed"])

    def test_a_grid_edit_names_the_changed_day(self):
        self.pull()
        path = runsheet.INSTANCE_DIR / "character" / "schedule.json"
        schedule = json.loads(path.read_text(encoding="utf-8"))
        current = schedule["schedule"]["0"][0]
        replacement = next(cell for cell in schedule["schedule"]["0"]
                           if cell and cell != current)
        schedule["schedule"]["0"][0] = replacement
        path.write_text(json.dumps(schedule, indent=2), encoding="utf-8")

        code, document, err = run_json("diff", "--json")
        self.assertEqual(code, 1, err)
        self.assertIn("0", document["payload"]["changes"]["grid"]["changedDays"])


class ValidateJsonTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)

        self._saved = (runsheet.INSTANCE_DIR, runsheet.detect_tier)
        runsheet.INSTANCE_DIR = self.tmp / "instance"
        runsheet.detect_tier = lambda config, probe=None: (1, "test")
        self.addCleanup(self._restore)

        document = json.loads(FIXTURE.read_text(encoding="utf-8"))
        model = runsheet.build_live_model(document["settings"], document["schedule"])
        runsheet.write_instance(model, {}, capture={
            "tier": 2, "at": "2026-10-31T00:00:00Z", "lossy": False, "lost": []})
        self.root = runsheet.INSTANCE_DIR

    def _restore(self):
        runsheet.INSTANCE_DIR, runsheet.detect_tier = self._saved

    def edit(self, *parts, mutate=None):
        path = self.root.joinpath(*parts)
        document = json.loads(path.read_text())
        mutate(document)
        path.write_text(json.dumps(document, indent=2))

    def persona_file(self):
        return sorted((self.root / "character" / "personas").glob("*.json"))[0]

    def test_a_valid_instance_reports_ok_and_zero_counts(self):
        code, document, err = run_json("validate", "--json")
        self.assertEqual(code, 0, err)
        self.assertEqual(document["command"], "validate")
        self.assertTrue(document["ok"])
        payload = document["payload"]
        self.assertEqual(payload["errors"], [])
        self.assertEqual(payload["warnings"], [])
        self.assertEqual(payload["issues"], [])
        self.assertEqual(payload["counts"]["errors"], 0)
        self.assertEqual(payload["counts"]["warnings"], 0)
        self.assertEqual(payload["counts"]["personas"], 2)
        self.assertEqual(payload["counts"]["shows"], 2)
        self.assertEqual(payload["counts"]["cells"], 168)
        self.assertEqual(payload["counts"]["filled"], 168)

    def test_an_error_is_listed_with_its_file_and_field(self):
        path = self.persona_file()
        self.edit("character", "personas", path.name, mutate=lambda d: d.pop("soul"))

        code, document, err = run_json("validate", "--json")
        self.assertEqual(code, 1, err)
        self.assertFalse(document["ok"])
        payload = document["payload"]
        self.assertGreaterEqual(payload["counts"]["errors"], 1)
        self.assertTrue(any(path.name in line and "soul" in line
                            for line in payload["errors"]))
        self.assertTrue(any(issue["severity"] == "error" and path.name in issue["message"]
                            for issue in payload["issues"]))

    def test_dir_targets_that_directory(self):
        demo = Path(__file__).resolve().parents[1] / "examples" / "demo"
        code, document, err = run_json("validate", "--dir", str(demo), "--json")
        self.assertEqual(code, 0, err)
        self.assertTrue(document["ok"])
        self.assertEqual(Path(document["payload"]["dir"]), demo)


if __name__ == "__main__":
    unittest.main()
