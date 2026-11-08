"""Tests for the `character` authoring group.

Everything runs in-process against the mock. The point of every test is the same
promise: a scaffold is valid the moment it exists, and it produces a coherent
apply plan without any hand-editing.
"""

import contextlib
import io
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

import mock_station
from test_runsheet import load_tool, scrub_station_environment

runsheet = load_tool()


class CharacterTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)

        self._saved_instance = runsheet.INSTANCE_DIR
        runsheet.INSTANCE_DIR = self.tmp / "instance"
        self.addCleanup(lambda: setattr(runsheet, "INSTANCE_DIR", self._saved_instance))

        self.server = mock_station.start_mock()
        self.addCleanup(self.server.stop)

        self._saved_environ = dict(os.environ)
        self.addCleanup(self._restore_environ)
        scrub_station_environment()
        os.environ.update({
            "SUBWAVE_BASE_URL": self.server.url,
            "SUBWAVE_ADMIN_USER": "mock-admin",
            "SUBWAVE_ADMIN_PASS": "mock-pass",
        })

    def _restore_environ(self):
        os.environ.clear()
        os.environ.update(self._saved_environ)

    # -- helpers -----------------------------------------------------------
    def run_cli(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                code = runsheet.main(list(args))
            except SystemExit as exc:  # argparse errors
                code = exc.code
        return code, out.getvalue() + err.getvalue()

    def validate(self):
        return self.run_cli("validate")

    def root(self):
        return runsheet.INSTANCE_DIR

    def assert_valid(self):
        code, output = self.validate()
        self.assertEqual(code, 0, output)
        self.assertIn("0 warning(s)", output)


class InitTests(CharacterTestCase):
    def test_blank_init_is_valid_immediately(self):
        code, output = self.run_cli("character", "init")
        self.assertEqual(code, 0, output)
        self.assert_valid()
        self.assertTrue((self.root() / "character" / "character.json").is_file())
        self.assertTrue((self.root() / "character" / "personas").is_dir())
        self.assertTrue((self.root() / "character" / "shows").is_dir())
        self.assertTrue((self.root() / "character" / "schedule.json").is_file())

    def test_demo_init_is_valid_immediately(self):
        code, output = self.run_cli("character", "init", "--from", "demo")
        self.assertEqual(code, 0, output)
        self.assert_valid()

    def test_init_records_an_authored_capture_not_a_tier(self):
        # Nothing was read from a station, so the lockfile must not claim a
        # tier. `lossy` is the only field that gates a write, and it is false.
        self.run_cli("character", "init")
        lock = json.loads((self.root() / "ids.lock.json").read_text())
        self.assertIsNone(lock["capture"]["tier"])
        self.assertFalse(lock["capture"]["lossy"])
        self.assertEqual(lock["capture"]["source"], "authored")

    def test_demo_init_is_not_a_tier_2_capture_either(self):
        self.run_cli("character", "init", "--from", "demo")
        lock = json.loads((self.root() / "ids.lock.json").read_text())
        self.assertIsNone(lock["capture"]["tier"])
        self.assertFalse(lock["capture"]["lossy"])

    def test_init_refuses_to_overwrite(self):
        self.run_cli("character", "init")
        code, output = self.run_cli("character", "init")
        self.assertEqual(code, 1)
        self.assertIn("already exists", output)

    def test_init_force_replaces(self):
        self.run_cli("character", "init")
        (self.root() / "character" / "personas" / "extra.json").write_text("{}")
        code, output = self.run_cli("character", "init", "--force")
        self.assertEqual(code, 0, output)
        self.assertFalse((self.root() / "character" / "personas" / "extra.json").exists())


class PersonaScaffoldTests(CharacterTestCase):
    def setUp(self):
        super().setUp()
        self.run_cli("character", "init")

    def test_new_persona_is_valid_and_has_all_eighteen_fields(self):
        code, output = self.run_cli("character", "new-persona", "dj-mira", "--name", "Mira Quell")
        self.assertEqual(code, 0, output)
        self.assert_valid()

        persona = json.loads((self.root() / "character" / "personas" / "dj-mira.json").read_text())
        self.assertEqual(len(persona), 18)
        self.assertEqual(persona["name"], "Mira Quell")
        self.assertIn("IDENTITY", persona["soul"])
        self.assertIn("VOICE", persona["soul"])
        self.assertIn("CATCHPHRASES", persona["soul"])

    def test_scaffolded_ids_satisfy_the_station_id_re(self):
        # The station's ID_RE forbids dashes; a dashed slug must still produce a
        # legal id, or the station rejects or normalises it on apply.
        code, output = self.run_cli("character", "new-persona", "dora-quint")
        self.assertEqual(code, 0, output)
        persona = json.loads((self.root() / "character" / "personas" / "dora-quint.json").read_text())
        self.assertEqual(persona["id"], "p_local_dora_quint")
        self.assertRegex(persona["id"], runsheet.ID_RE)
        self.assertNotIn("-", persona["id"])

    def test_new_persona_refuses_a_duplicate_slug(self):
        self.run_cli("character", "new-persona", "dj-mira")
        code, output = self.run_cli("character", "new-persona", "dj-mira")
        self.assertEqual(code, 1)
        self.assertIn("already exists", output)

    def test_new_persona_produces_a_coherent_dry_run(self):
        self.run_cli("character", "new-persona", "dj-mira")
        before = len(self.server.station.requests)
        code, output = self.run_cli("apply")
        self.assertEqual(code, 0, output)
        self.assertIn("dry run", output)
        self.assertIn("0 requests sent", output)
        self.assertIn("2 personas", output)
        self.assertEqual(len(self.server.station.requests), before)


class ShowScaffoldTests(CharacterTestCase):
    def setUp(self):
        super().setUp()
        self.run_cli("character", "init")
        self.run_cli("character", "new-persona", "dj-mira")

    def test_new_show_is_valid_and_has_all_twenty_six_fields(self):
        code, output = self.run_cli("character", "new-show", "harbour-mornings",
                                    "--name", "Harbour Mornings", "--persona", "dj-mira")
        self.assertEqual(code, 0, output)
        self.assert_valid()

        show = json.loads((self.root() / "character" / "shows" / "harbour-mornings.json").read_text())
        self.assertEqual(len(show), 26)
        self.assertFalse(show["banter"])
        self.assertEqual(show["playlistIds"], [])
        lock = json.loads((self.root() / "ids.lock.json").read_text())
        self.assertEqual(show["personaId"], lock["personas"]["dj-mira"])

    def test_scaffolded_show_id_satisfies_the_station_id_re(self):
        code, output = self.run_cli("character", "new-show", "late-harbour-two", "--persona", "dj-mira")
        self.assertEqual(code, 0, output)
        show = json.loads((self.root() / "character" / "shows" / "late-harbour-two.json").read_text())
        self.assertEqual(show["id"], "s_local_late_harbour_two")
        self.assertRegex(show["id"], runsheet.ID_RE)

    def test_new_show_needs_a_persona_when_several_exist(self):
        code, output = self.run_cli("character", "new-show", "no-host")
        self.assertEqual(code, 1)
        self.assertIn("--persona is required", output)

    def test_new_show_produces_a_coherent_dry_run(self):
        self.run_cli("character", "new-show", "harbour-mornings", "--persona", "dj-mira")
        before = len(self.server.station.requests)
        code, output = self.run_cli("apply")
        self.assertEqual(code, 0, output)
        self.assertIn("show harbour-mornings", output)
        self.assertIn("26 fields", output)
        self.assertEqual(len(self.server.station.requests), before)


class GridTests(CharacterTestCase):
    def setUp(self):
        super().setUp()
        self.run_cli("character", "init")
        self.run_cli("character", "new-persona", "dj-mira")
        self.run_cli("character", "new-show", "harbour-mornings", "--persona", "dj-mira")

    def grid(self):
        return json.loads((self.root() / "character" / "schedule.json").read_text())["schedule"]

    def test_add_to_grid_fills_the_named_hours(self):
        code, output = self.run_cli("character", "add-to-grid", "harbour-mornings",
                                    "--days", "mon,tue", "--from", "9", "--to", "12", "--replace")
        self.assertEqual(code, 0, output)
        self.assertIn("mon 09:00", output)
        self.assertIn("mon 11:00", output)
        self.assertNotIn("mon 12:00", output)
        grid = self.grid()
        self.assertEqual(grid["1"][9:12], ["harbour-mornings"] * 3)
        self.assertEqual(grid["2"][9:12], ["harbour-mornings"] * 3)
        self.assertEqual(grid["1"][8], "first-show")
        self.assert_valid()

    def test_add_to_grid_refuses_an_occupied_cell(self):
        before = self.grid()
        code, output = self.run_cli("character", "add-to-grid", "harbour-mornings",
                                    "--days", "mon", "--from", "9", "--to", "10")
        self.assertEqual(code, 1)
        self.assertIn("already hold another show", output)
        self.assertIn("first-show", output, "the refusal must show what would change")
        self.assertEqual(self.grid(), before, "a refusal must not write")

    def test_add_to_grid_replace_takes_the_cells(self):
        code, output = self.run_cli("character", "add-to-grid", "harbour-mornings",
                                    "--days", "mon", "--from", "9", "--to", "10", "--replace")
        self.assertEqual(code, 0, output)
        self.assertEqual(self.grid()["1"][9], "harbour-mornings")

    def test_add_to_grid_rejects_a_bad_range(self):
        code, output = self.run_cli("character", "add-to-grid", "harbour-mornings",
                                    "--days", "mon", "--from", "12", "--to", "9")
        self.assertEqual(code, 1)
        self.assertIn("earlier than", output)


class RoundTripTests(CharacterTestCase):
    def test_a_scaffolded_persona_survives_a_full_apply(self):
        self.run_cli("character", "init")
        self.run_cli("character", "new-persona", "dj-mira", "--name", "Mira Quell")

        code, output = self.run_cli("apply", "--yes", "--force-now", "--no-backup")
        self.assertEqual(code, 0, output)

        sent = [entry["body"]["personas"] for entry in self.server.station.requests
                if entry["path"] == "/api/settings" and "personas" in (entry["body"] or {})]
        self.assertTrue(sent)
        persona = next(p for p in sent[0] if p["name"] == "Mira Quell")
        self.assertEqual(len(persona), 18, "a scaffolded persona must be sent whole")
        self.assertIn("IDENTITY", persona["soul"])

        stored = next(p for p in self.server.station.settings["personas"]
                      if p["name"] == "Mira Quell")
        self.assertEqual(len(stored), 18)
        self.assertEqual(stored["humour"], 5)

    def test_a_scaffolded_show_gets_a_real_id_on_apply(self):
        self.run_cli("character", "init")
        self.run_cli("character", "new-persona", "dj-mira")
        self.run_cli("character", "new-show", "harbour-mornings", "--persona", "dj-mira")

        path = self.root() / "character" / "shows" / "harbour-mornings.json"
        self.assertTrue(json.loads(path.read_text())["id"].startswith("s_local_"))

        code, output = self.run_cli("apply", "--yes", "--force-now", "--no-backup")
        self.assertEqual(code, 0, output)

        assigned = json.loads(path.read_text())["id"]
        self.assertTrue(assigned.startswith("s_"))
        self.assertFalse(assigned.startswith("s_local_"), "the station must assign a real id")
        lock = json.loads((self.root() / "ids.lock.json").read_text())
        self.assertEqual(lock["shows"]["harbour-mornings"], assigned)


class SharedEnvFileIsScrubbedTests(CharacterTestCase):
    """A developer's RUNSHEET_ENV_FILE must not let the suite reach a station.

    setUpClass runs before setUp, so the variable is in os.environ when the
    fixture starts - exactly the state an orchestrator creates by exporting it.
    The fixture's scrub is what keeps apply at tier 1; without it Config() would
    take SUBWAVE_HOST and SUBWAVE_STATE_DIR from the shared file and apply would
    ssh to the live host.
    """

    @classmethod
    def setUpClass(cls):
        cls.shared_dir = Path(tempfile.mkdtemp())
        cls.shared_env = cls.shared_dir / "station.env"
        cls.shared_env.write_text(
            "SUBWAVE_HOST=live@station\nSUBWAVE_STATE_DIR=/var/sub-wave\n",
            encoding="utf-8")
        cls._saved_env_file = os.environ.get(runsheet.ENV_FILE_VAR)
        os.environ[runsheet.ENV_FILE_VAR] = str(cls.shared_env)

    @classmethod
    def tearDownClass(cls):
        if cls._saved_env_file is None:
            os.environ.pop(runsheet.ENV_FILE_VAR, None)
        else:
            os.environ[runsheet.ENV_FILE_VAR] = cls._saved_env_file
        shutil.rmtree(cls.shared_dir, True)

    def test_apply_stays_tier_1_and_never_touches_ssh(self):
        self.assertNotIn(runsheet.ENV_FILE_VAR, os.environ,
                         "the fixture must scrub the shared credentials pointer")

        def refuse(*args, **kwargs):
            raise AssertionError("the suite is offline: apply must not ssh")

        saved = runsheet.ssh_run, runsheet.ssh_probe
        runsheet.ssh_run = refuse
        runsheet.ssh_probe = refuse
        self.addCleanup(lambda: setattr(runsheet, "ssh_run", saved[0]))
        self.addCleanup(lambda: setattr(runsheet, "ssh_probe", saved[1]))

        self.run_cli("character", "init")
        before = len(self.server.station.requests)
        code, output = self.run_cli("apply")
        self.assertEqual(code, 0, output)
        self.assertIn("dry run", output)
        self.assertIn("0 requests sent", output)
        self.assertEqual(len(self.server.station.requests), before)


if __name__ == "__main__":
    unittest.main()
