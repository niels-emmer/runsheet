"""Native skill discovery is wired by symlink, so the wiring needs a test.

`AGENTS.md` said the discovery links "cannot drift", but nothing checked: a sixth
`skills/<name>/SKILL.md` could land with no links (invisible to every loader),
and an editor that saves by writing a temp file and renaming it over the path —
or a `core.symlinks=false` checkout committed back — turns a link into a regular
file, a full copy of the procedure that then drifts. Both pass every other
check in this repo, because the damage looks like nothing more than a
`120000 -> 100644` mode change in a diff nobody reads.

The expected set is built from `git ls-files`, never from a directory listing:
agent harnesses drop their own untracked skills into these directories (AO
writes `.opencode/skills/using-ao/`, and its `.claude/` hook files), and a
listing-based test would fail on another machine's harness rather than on this
repo's links.
"""

import os
import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Each tool-owned path and the exact relative target it must hold. The two forms
# differ because the loaders document different things: Claude Code scans
# `<dir>/<name>/SKILL.md`, while Codex's docs describe following symlinked skill
# *folders* (`$CWD/.agents/skills` up to the repo root). OpenCode reads both
# directories as project compatibility sources, so neither needs its own copy.
LINKS = (
    (".claude/skills/{name}/SKILL.md", "../../../skills/{name}/SKILL.md"),
    (".agents/skills/{name}", "../../skills/{name}"),
)

SYMLINK_MODE = "120000"


def git(*args):
    result = subprocess.run(("git",) + args, cwd=ROOT, capture_output=True, check=True)
    return [entry for entry in result.stdout.decode().split("\0") if entry]


def tracked_modes(pathspec):
    """Tracked path -> git mode. Untracked entries are absent by construction."""
    modes = {}
    for entry in git("ls-files", "-s", "-z", "--", pathspec):
        meta, name = entry.split("\t", 1)
        modes[name] = meta.split()[0]
    return modes


class SkillDiscoveryTests(unittest.TestCase):
    """Every procedure is one symlink away from each loader that reads a directory."""

    def skills(self):
        names = {
            match.group(1)
            for match in (re.fullmatch(r"skills/([^/]+)/SKILL\.md", name)
                          for name in git("ls-files", "-z", "--", "skills"))
            if match
        }
        self.assertTrue(names, "no tracked skills/<name>/SKILL.md found")
        return names

    def test_every_skill_is_linked_into_every_tool_directory(self):
        modes = tracked_modes(".claude/skills")
        modes.update(tracked_modes(".agents"))
        for name in sorted(self.skills()):
            for template, target_template in LINKS:
                link = template.format(name=name)
                target = target_template.format(name=name)
                with self.subTest(link=link):
                    self.assertEqual(
                        modes.get(link), SYMLINK_MODE,
                        "%s must be a committed symlink (mode %s); mode %s means a copy or "
                        "nothing. A real file here is a second copy of the procedure."
                        % (link, SYMLINK_MODE, modes.get(link, "absent")))
                    self.assertEqual(
                        os.readlink(ROOT / link), target,
                        "%s must point at %s, the same relative target from any checkout"
                        % (link, target))
                    self.assertEqual(
                        os.path.realpath(ROOT / link),
                        os.path.realpath((ROOT / link).parent / target),
                        "%s does not resolve to its target" % link)

    def test_no_link_points_at_a_missing_skill(self):
        expected = {
            template.format(name=name)
            for name in self.skills()
            for template, _ in LINKS
        }
        linked = {
            path for path, mode in
            list(tracked_modes(".claude/skills").items()) + list(tracked_modes(".agents").items())
            if mode == SYMLINK_MODE
        }
        self.assertEqual(
            linked - expected, set(),
            "symlinks with no skills/<name>/SKILL.md behind them, left by a "
            "deleted skill: %s" % ", ".join(sorted(linked - expected)))

    def test_every_skill_has_a_row_in_the_routing_table(self):
        agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        section = agents.split("## Which procedure to load", 1)
        self.assertEqual(len(section), 2, "AGENTS.md has no 'Which procedure to load' section")
        table = section[1].split("\n## ", 1)[0]
        for name in sorted(self.skills()):
            with self.subTest(skill=name):
                self.assertIn(
                    "| `%s` |" % name, table,
                    "%s has no row in the AGENTS.md routing table, so an agent whose "
                    "loader is not one of the linked directories cannot find it" % name)


if __name__ == "__main__":
    unittest.main()
