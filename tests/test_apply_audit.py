"""`apply --yes` must leave one audit entry and one index row per verified apply.

The audit trail is a file per entry under docs/applied/ plus an index table in
docs/applied.md. These tests drive the real `cmd_apply` against
tests/mock_station.py and read both back. The path is redirected to a temp tree:
a test must never write to the repository's own audit trail.
"""

import json
import re
import shutil
import unittest
from datetime import datetime, timezone
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

# `load_tool()` builds a fresh module on every call, so use the exact module
# object the shared harness patches; a second copy would leave both the audit
# path and INSTANCE_DIR redirected in the wrong one.
from test_apply import ApplyTestCase, runsheet

LINK_RE = re.compile(r"^\[(.+)\]\(applied/([^)]+\.md)\)$")


def data_rows(text):
    """The index table's data rows, as cell lists. Header and separator excluded."""
    rows = []
    for line in text.splitlines():
        if not line.startswith("|") or line.startswith("| Date |"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if all(set(cell) <= set("-: ") for cell in cells):
            continue
        rows.append(cells)
    return rows


def entry_fields(text):
    """The six bullet fields of an entry file, keyed by name."""
    fields = {}
    for line in text.splitlines():
        match = re.match(r"^- \*\*(.+?):\*\* (.*)$", line)
        if match:
            fields[match.group(1)] = match.group(2)
    return fields


class AuditTestCase(ApplyTestCase):
    def setUp(self):
        super().setUp()
        self.docs = self.tmp / "docs"
        self.docs.mkdir()
        self.entries = self.docs / "applied"
        # Start from the real document and its real entry so the test proves
        # the append matches what actually lives in the repo.
        source = Path(runsheet.REPO_ROOT) / "docs"
        shutil.copytree(source / "applied", self.entries)
        self.doc = self.docs / "applied.md"
        self.doc.write_text((source / "applied.md").read_text(encoding="utf-8"),
                            encoding="utf-8")
        saved = runsheet.APPLIED_DOC
        runsheet.APPLIED_DOC = self.doc
        self.addCleanup(setattr, runsheet, "APPLIED_DOC", saved)
        self.baseline = self.doc.read_text(encoding="utf-8")
        self.baseline_entries = sorted(path.name for path in self.entries.glob("*.md"))

    def rows(self):
        return data_rows(self.doc.read_text(encoding="utf-8"))

    def entry_names(self):
        return sorted(path.name for path in self.entries.glob("*.md"))

    def new_entries(self):
        return sorted(set(self.entry_names()) - set(self.baseline_entries))

    def read_entry(self, name):
        return (self.entries / name).read_text(encoding="utf-8")


class SuccessfulApplyTests(AuditTestCase):
    def test_a_verified_apply_writes_one_entry_and_one_index_row(self):
        before_rows = len(self.rows())
        code, output = self.run_apply(yes=True)
        self.assertEqual(code, 0, output)

        new = self.new_entries()
        self.assertEqual(len(new), 1, "one apply, one entry file")
        name = new[0]
        self.assertRegex(name, r"^\d{4}-\d{2}-\d{2}-auto-apply-\d{6}Z\.md$")

        rows = self.rows()
        self.assertEqual(len(rows), before_rows + 1, "one apply, one index row")
        date, link = rows[-1]
        self.assertRegex(date, r"^\d{4}-\d{2}-\d{2}$")
        self.assertTrue(date in name, "the index date must match the entry file")
        match = LINK_RE.match(link)
        self.assertIsNotNone(match, "the index row must link to the entry: %r" % link)
        self.assertEqual(match.group(2), name)

        fields = entry_fields(self.read_entry(name))
        self.assertEqual(set(fields), set(runsheet.APPLIED_FIELDS),
                         "the entry must carry every documented field")
        self.assertRegex(fields["Date"], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
        self.assertTrue(fields["Commit"] == "—" or len(fields["Commit"]) >= 7)
        for word in ("shows", "grid", "settings"):
            self.assertIn(word, fields["What changed"])
        self.assertIn("168 cells", fields["What changed"])
        self.assertIn("--no-backup", fields["Backup ref"])
        self.assertIn("read-back passed", fields["Verified by"])
        self.assertIn("NOT verified", fields["Verified by"],
                      "tier 1 must not claim a full verification")
        self.assertIn("not checked", fields["Listener check"])

        self.assertIn("audit     ", output)
        self.assertIn("+ index row", output)

    def test_a_dry_run_writes_nothing(self):
        code, _ = self.run_apply()
        self.assertEqual(code, 0)
        self.assertEqual(self.doc.read_text(encoding="utf-8"), self.baseline)
        self.assertEqual(self.new_entries(), [])

    def test_a_no_op_second_apply_adds_no_second_entry(self):
        self.run_apply(yes=True)
        once = len(self.rows())
        code, output = self.run_apply(yes=True)
        self.assertEqual(code, 0)
        self.assertIn("no changes", output)
        self.assertEqual(len(self.rows()), once, "a no-op apply changed nothing to record")
        self.assertEqual(len(self.new_entries()), 1)

    def test_existing_entries_are_left_alone(self):
        self.run_apply(yes=True)
        self.assertIn(self.baseline, self.doc.read_text(encoding="utf-8"),
                      "the index only ever grows")
        for name in self.baseline_entries:
            self.assertTrue((self.entries / name).is_file())

    def test_the_entry_does_not_repeat_a_secret(self):
        settings_path = runsheet.INSTANCE_DIR / "settings.json"
        document = json.loads(settings_path.read_text())
        document["privacy"]["password"] = runsheet.SENTINEL
        settings_path.write_text(json.dumps(document, indent=2))

        code, output = self.run_apply(
            config=self.config(SUBWAVE_STATION_PASSWORD="an-audit-secret"), yes=True)
        self.assertEqual(code, 0, output)
        name = self.new_entries()[0]
        self.assertNotIn("an-audit-secret", self.read_entry(name),
                         "the audit trail must not acquire a credential")
        self.assertNotIn("an-audit-secret", self.doc.read_text(encoding="utf-8"))

    def test_a_same_second_entry_is_not_overwritten(self):
        class FrozenDatetime(datetime):
            @classmethod
            def now(cls, tz=None):
                return cls(2026, 11, 8, 4, 5, 6, tzinfo=timezone.utc)

        saved = runsheet.datetime
        runsheet.datetime = FrozenDatetime
        self.addCleanup(setattr, runsheet, "datetime", saved)
        taken = self.entries / "2026-11-08-auto-apply-040506Z.md"
        taken.write_text("# a hand-written entry\n", encoding="utf-8")

        code, output = self.run_apply(yes=True)
        self.assertEqual(code, 0, output)
        self.assertEqual(taken.read_text(encoding="utf-8"), "# a hand-written entry\n")
        self.assertIn("2026-11-08-auto-apply-040506Z-2.md", self.new_entries())
        self.assertIn("2026-11-08-auto-apply-040506Z-2.md", self.rows()[-1][1])


class FailedApplyTests(AuditTestCase):
    def test_a_read_back_mismatch_writes_no_entry(self):
        # Rename a persona, then let the station accept the write and store
        # nothing: the exact silent no-op verification exists to catch.
        path = sorted((runsheet.INSTANCE_DIR / "character" / "personas").glob("*.json"))[0]
        document = json.loads(path.read_text())
        document["name"] = "Ghost Host"
        path.write_text(json.dumps(document, indent=2))

        original = self.server.station.merge_settings

        def drops_personas(body):
            return original({key: value for key, value in body.items() if key != "personas"})

        self.server.station.merge_settings = drops_personas

        with self.assertRaises(runsheet.ToolError) as caught:
            self.run_apply(yes=True)
        self.assertIn("did NOT land", str(caught.exception))
        self.assertEqual(self.doc.read_text(encoding="utf-8"), self.baseline,
                         "a failed verification must not add an entry claiming success")
        self.assertEqual(self.new_entries(), [])

    def test_a_refused_apply_writes_nothing(self):
        with self.assertRaises(runsheet.ToolError):
            self.run_apply(yes=True, force_now=False)
        self.assertEqual(self.doc.read_text(encoding="utf-8"), self.baseline)
        self.assertEqual(self.new_entries(), [])


class MissingAuditDocumentTests(AuditTestCase):
    def test_a_checkout_without_docs_skips_the_write_with_a_warning(self):
        missing = self.tmp / "no-docs" / "applied.md"
        runsheet.APPLIED_DOC = missing

        code, output = self.run_apply(yes=True)
        self.assertEqual(code, 0, "the apply already landed; a missing audit file must not fail it")
        self.assertIn("audit     skipped", output)
        self.assertIn("does not exist", output)
        self.assertFalse(missing.exists(), "no audit file should be invented")
        self.assertFalse((self.tmp / "no-docs" / "applied").exists())

    def test_an_index_without_the_table_is_skipped_not_corrupted(self):
        self.doc.write_text("# someone's notes\n\nno table here\n", encoding="utf-8")
        before = self.entry_names()
        code, output = self.run_apply(yes=True)
        self.assertEqual(code, 0)
        self.assertIn("has no '| Date |' audit table", output)
        self.assertEqual(self.doc.read_text(encoding="utf-8"),
                         "# someone's notes\n\nno table here\n")
        self.assertEqual(self.entry_names(), before,
                         "a skipped index append must not leave an unindexed entry")


if __name__ == "__main__":
    unittest.main()
