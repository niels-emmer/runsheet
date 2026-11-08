"""Where credentials are loaded from.

`.env` lives in the checkout and is gitignored, so an orchestrator running many
ephemeral worktrees against one station had to recreate it everywhere.
`RUNSHEET_ENV_FILE` names one file outside any checkout instead. These tests pin
the contract: real environment > the named file > ./.env, and the named file
replaces .env rather than merging with it.
"""

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_runsheet import load_tool

runsheet = load_tool()
REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "runsheet.py"


class EnvFileTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def credentials(self, name, **values):
        path = self.tmp / name
        path.write_text("".join("%s=%s\n" % item for item in values.items()))
        return path

    def repo_with_dotenv(self, **values):
        """A stand-in checkout whose .env holds `values`."""
        repo = self.tmp / "repo"
        repo.mkdir(exist_ok=True)
        repo.joinpath(".env").write_text(
            "".join("%s=%s\n" % item for item in values.items()))
        patcher = mock.patch.object(runsheet, "REPO_ROOT", repo)
        patcher.start()
        self.addCleanup(patcher.stop)
        return repo

    # -- the named file is read -------------------------------------------
    def test_a_file_outside_the_repo_is_loaded(self):
        shared = self.credentials(
            "shared.env",
            SUBWAVE_BASE_URL="http://station.example:7700",
            SUBWAVE_ADMIN_USER="admin",
            SUBWAVE_HOST="radio@host",
            SUBWAVE_STATE_DIR="/var/sub-wave/",
        )
        config = runsheet.Config(environ={runsheet.ENV_FILE_VAR: str(shared)})
        self.assertEqual(config.base_url, "http://station.example:7700")
        self.assertEqual(config.admin_user, "admin")
        self.assertEqual(config.host, "radio@host")
        self.assertEqual(config.state_dir, "/var/sub-wave")

    def test_a_named_file_wins_over_the_repo_dotenv(self):
        self.repo_with_dotenv(SUBWAVE_ADMIN_USER="stale")
        shared = self.credentials("shared.env", SUBWAVE_ADMIN_USER="shared")
        config = runsheet.Config(environ={runsheet.ENV_FILE_VAR: str(shared)})
        self.assertEqual(config.admin_user, "shared")

    def test_the_named_file_replaces_the_dotenv_instead_of_merging(self):
        # SUBWAVE_HOST exists only in .env. An ephemeral worktree must not pick
        # up a second, stale source; a missing key stays missing.
        self.repo_with_dotenv(SUBWAVE_HOST="stale@host")
        shared = self.credentials("shared.env", SUBWAVE_BASE_URL="http://shared")
        config = runsheet.Config(environ={runsheet.ENV_FILE_VAR: str(shared)})
        self.assertEqual(config.host, "")

    # -- precedence ---------------------------------------------------------
    def test_the_real_environment_beats_the_named_file(self):
        shared = self.credentials(
            "shared.env",
            SUBWAVE_BASE_URL="http://from-file",
            SUBWAVE_ADMIN_USER="file-admin",
        )
        config = runsheet.Config(environ={
            runsheet.ENV_FILE_VAR: str(shared),
            "SUBWAVE_BASE_URL": "http://from-env",
        })
        self.assertEqual(config.base_url, "http://from-env")
        self.assertEqual(config.admin_user, "file-admin")

    def test_an_empty_variable_counts_as_unset(self):
        self.repo_with_dotenv(SUBWAVE_ADMIN_USER="from-dotenv")
        config = runsheet.Config(environ={runsheet.ENV_FILE_VAR: "  "})
        self.assertEqual(config.admin_user, "from-dotenv")

    # -- fallback is unchanged ---------------------------------------------
    def test_unset_falls_back_to_the_repo_dotenv(self):
        self.repo_with_dotenv(SUBWAVE_BASE_URL="http://dotenv", SUBWAVE_ADMIN_PASS="pw")
        config = runsheet.Config(environ={})
        self.assertEqual(config.base_url, "http://dotenv")
        self.assertEqual(config.admin_pass, "pw")

    def test_unset_with_no_dotenv_yields_empty_config(self):
        repo = self.tmp / "bare"
        repo.mkdir()
        with mock.patch.object(runsheet, "REPO_ROOT", repo):
            config = runsheet.Config(environ={})
        self.assertEqual(config.base_url, "")

    # -- loud failure -------------------------------------------------------
    def test_a_missing_named_file_is_a_config_error(self):
        missing = str(self.tmp / "nope.env")
        with self.assertRaises(runsheet.ConfigError):
            runsheet.Config(environ={runsheet.ENV_FILE_VAR: missing})

    def test_the_cli_reports_a_missing_named_file_without_a_traceback(self):
        env = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            runsheet.ENV_FILE_VAR: str(self.tmp / "nope.env"),
        }
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "validate", "--dir", "examples/demo"],
            cwd=REPO_ROOT, env=env, capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, runsheet.EXIT_CONFIG, result.stderr)
        self.assertIn(runsheet.ENV_FILE_VAR, result.stderr)
        self.assertNotIn("Traceback", result.stderr)


if __name__ == "__main__":
    unittest.main()
