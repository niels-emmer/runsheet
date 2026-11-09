"""The container image is a runtime, not a second install path (D14).

These checks need no Docker daemon, so the suite stays offline: they pin the
properties the image has to keep as text. The one that matters most is that the
image copies nothing from the checkout. A `COPY . .` added for convenience
would bake a copy of `scripts/runsheet.py` into the image, giving it its own
`REPO_ROOT`, its own `instance/` and its own idea of which commit is running —
the second source of truth D1 exists to prevent. Started from a working
checkout it would also bake `.env`, whose whole promise is that it never leaves
the machine.
"""

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCKERFILE = ROOT / "Dockerfile"
DOCKERIGNORE = ROOT / ".dockerignore"
WORKFLOW = ROOT / ".github" / "workflows" / "image.yml"


def instructions(path):
    """The Dockerfile without comments and blank lines."""
    lines = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line and not line.startswith("#"):
            lines.append(line)
    return lines


def ignore_patterns(path):
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.strip().startswith("#")]


class ImageTests(unittest.TestCase):
    def setUp(self):
        for path in (DOCKERFILE, DOCKERIGNORE, WORKFLOW):
            if not path.is_file():
                self.fail("%s is missing" % path)
        self.dockerfile = DOCKERFILE.read_text(encoding="utf-8")

    def test_the_image_copies_nothing_from_the_checkout(self):
        offenders = [line for line in instructions(DOCKERFILE)
                     if re.match(r"(?i)^(COPY|ADD)\b", line)]
        self.assertEqual(
            offenders, [],
            "the image is a runtime: it must not copy the checkout in (%s). "
            "See docs/decisions/D14." % "; ".join(offenders))

    def test_the_entrypoint_is_the_cli_from_the_mount(self):
        self.assertIn('ENTRYPOINT ["python3", "scripts/runsheet.py"]', self.dockerfile)
        self.assertIn("WORKDIR /repo", self.dockerfile)

    def test_the_image_runs_unprivileged(self):
        users = [line for line in instructions(DOCKERFILE) if line.upper().startswith("USER ")]
        self.assertEqual(len(users), 1, "expected exactly one USER instruction, got %r" % users)
        value = users[0].split(None, 1)[1].strip()
        self.assertRegex(value, r"^\d+:\d+$", "USER must be a numeric uid:gid, got %r" % value)
        self.assertNotEqual(value.split(":")[0], "0", "the image must not run as root")

    def test_the_base_image_is_the_supported_python_runtime(self):
        bases = [line for line in instructions(DOCKERFILE) if line.upper().startswith("FROM ")]
        self.assertEqual(len(bases), 1, "expected a single FROM, got %r" % bases)
        # A digest pin is allowed and encouraged; the tag alone is the floor.
        self.assertRegex(bases[0], r"^FROM python:3\.\d+-alpine(@sha256:[0-9a-f]{64})?$")

    def test_the_build_context_excludes_credentials_and_station_data(self):
        patterns = ignore_patterns(DOCKERIGNORE)
        for required in (".env", ".env.*", "instance/", "backups/"):
            self.assertIn(required, patterns,
                          ".dockerignore must exclude %r: a build started from a working "
                          "checkout would otherwise hand it to the daemon" % required)

    def test_the_image_is_published_only_from_a_release_tag(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("refs/tags/v", text, "publishing must be gated on a release tag")
        self.assertIn("ghcr.io", text)
        self.assertIn("linux/arm64", text, "a station host may be a Raspberry Pi")


if __name__ == "__main__":
    unittest.main()
