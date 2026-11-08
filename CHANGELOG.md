# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **`capabilities` says what the current tier can do, without attempting it.** A new read-only
  subcommand reuses `status`'s tier detection and reports, for every top-level verb (`pull`, `diff`,
  `backup`, `restore`, `apply`, `apply --prune`, `character`, `skills`, `blocklist`, `onair`), whether
  it is available and, if not, why — mirroring `AGENTS.md`'s tier table and the refusals the write
  commands already enforce: `backup` and `restore` are refused at tier 1 (no `schedule.json`), and
  `apply --prune` needs host access. A verb that works but is degraded says so (`pull` is lossy at
  tier 1, `apply` needs `--no-backup`). `--json` emits `{"tier": …, "capabilities": {…}}` so an
  orchestrator can decide whether a task is possible before spawning a worker. It changes no other
  command's output and attempts no network or ssh operation.
- **`--mock` runs any station command against the in-process mock station.** `tests/mock_station.py` was
  reachable only from the test suite; now `status`, `pull`, `diff`, `apply`, `backup`, `restore` and
  `onair` accept `--mock` (before or after the command) and the tool starts that same mock itself, on
  loopback, as a tier-2 station. Nothing leaves the machine: no network, no ssh, and no `SUBWAVE_*` value
  from the environment or `.env` is consulted. The module is imported lazily, so the live path never loads
  it. A real `apply --yes --mock` executes the full pre-write backup, write, and read-back verification and
  prints what a live apply would, which is how a multi-field change can be rehearsed before it touches a
  station. See [`tests/test_mock_mode.py`](tests/test_mock_mode.py).
- **`RUNSHEET_ENV_FILE` loads credentials from outside the checkout.** Point it at a `KEY=VALUE` file
  and runsheet reads `SUBWAVE_*` from there instead of `./.env`, so an orchestrator running many ephemeral
  git worktrees against one station no longer has to recreate `.env` in each. Precedence is exported
  variables, then the named file, then `./.env`; the named file replaces `.env` rather than merging with
  it, and a set-but-missing path fails as a configuration error instead of silently falling back.
  Documented in `.env.example` and the README's "Getting started"; pinned by
  [`tests/test_env_file.py`](tests/test_env_file.py).
- **`apply --yes` records itself in `docs/applied/`.** After the post-apply read-back proves the
  writes landed, the tool writes one audit entry (`<YYYY-MM-DD>-auto-apply-<HHMMSSZ>.md`) and adds its
  index row to `docs/applied.md`, naming the UTC time, the checkout commit, what actually differed
  (personas, shows, settings keys, character fields, grid days, override, blocklist entries and rules,
  skills — compared against the station before the write, since apply always sends whole objects) and what
  the read-back could and could not verify. The trail previously depended on someone remembering to type the entry, so it drifted from the
  station the first time a run was forgotten. A dry run and a failed verification write nothing, existing
  entries are never rewritten, and a checkout without `docs/` (an `instance/`-only fork) skips the write
  with a warning instead of failing an apply that already landed. Pinned by
  [`tests/test_apply_audit.py`](tests/test_apply_audit.py), which uses the shared mock station.
- **Tier 2 is reachable from a bare ssh host.** `status` at tier 1 now probes the host it is given: one
  read-only ssh round trip lists the running containers, inspects their mounts, and reports the first
  mount that already contains a `settings.json`, printing the exact `SUBWAVE_CONTAINER=` and
  `SUBWAVE_STATE_DIR=` lines to add. A wrong container name on the right host is recovered the same way.
  Without `SUBWAVE_HOST` it says what to set and probes nothing. See
  [D13](docs/decisions/D13-tier-2-is-discovered-from-a-bare-ssh-host-not-interrogated-out-of-the-operator.md).
- [`tests/test_onboarding.py`](tests/test_onboarding.py) pins the discovery contract — parsing, ordering
  (the image default leads), remote-shell noise, an unreachable host, and every `status` message — with
  `ssh_run` stubbed, so it needs no ssh.
- `AGENTS.md` gains a **Which procedure to load** table. No agent scans a repo-root `skills/` automatically
  (Claude Code reads `.claude/skills/`, OpenCode `.opencode/skills/` and `.agents/skills/`, Codex
  `.agents/skills`), so the table is the discovery surface rather than an unread directory.
- The README names the station's own MCP endpoint as the **no-checkout door**: `/api/mcp`, 21 tools, reads
  plus on-air control — and states plainly that it has no diff, no dry run, no backup and no undo, and
  cannot touch configuration.

### Changed

- **Claude Code, Codex and OpenCode now discover the five skills natively.**
  `.claude/skills/<name>/SKILL.md` is a committed relative symlink to `../../../skills/<name>/SKILL.md`, and
  `.agents/skills/<name>` is a relative symlink to the skill's folder (`../../skills/<name>`) — the location
  Codex scans from the working directory up to the repo root, in the form its docs describe following through
  a symlink. OpenCode reads both as project compatibility sources, so two directories cover all three agents
  and every loader finds `add-host`, `new-show`, `explain-host`, `tune-host` and `backup` without an agent
  having read `AGENTS.md` first. Symlinks rather than generated pointer files: git stores them as mode
  `120000`, a relative target resolves from a plain clone and from a linked worktree, and there is no second
  file to regenerate or let drift. [`tests/test_skill_discovery.py`](tests/test_skill_discovery.py) pins all
  three surfaces for every tracked skill, so a link replaced by a real copy fails the suite. The `AGENTS.md`
  table stays the routing surface for any other agent, and for these it remains the authority on the
  verb-decides rule.
- **The decision log and the applied log are now one entry per file.** [`docs/decision-log.md`](docs/decision-log.md)
  and [`docs/applied.md`](docs/applied.md) are indexes; each decision lives at
  `docs/decisions/D<n>-<slug>.md` and each applied row at `docs/applied/<date>-<slug>.md`. Both logs were
  append-only files that every contributor edited at the end, so two branches that each added an entry
  conflicted on every rebase for no reason — and this repo is developed by parallel agent sessions in
  separate worktrees, which makes that constant. Every existing entry moved across verbatim, and links
  that named a specific decision now point at its file. `apply` writing its own audit entry is separate
  work; the directory is the shape it will write into.
- **Renamed from `subwave-marvin` to `runsheet`.** The script is now `scripts/runsheet.py` and the repo
  `niels-emmer/runsheet`. The old name implied this tool was part of the SUB/WAVE project; it is not.
  `SUB/WAVE` and the `SUBWAVE_*` variables still name the station, not the tool, and are unchanged.
- The README's "Getting started" starts at `git clone`. It did not before: it opened with `python3` and
  `.env`, so a stranger's first step was missing, and `tests/test_smoke.py` could not catch it because the
  smoke test begins *after* the clone.
- The tier-1 honest note is now a decision rather than a caveat. Web address only = author from scratch;
  a lossy capture of a live station is refused by `apply` and the README says so.
- `status` no longer claims "this build is read-only" — `apply` and `onair` have both been able to write for
  some time, so the line was false.
- `character init` records an **authored** capture (`tier: null`, `source: "authored"`) instead of
  hardcoding `tier: 2` for files that were never read from a station. `examples/demo/ids.lock.json` matches.
- `docs/PLAN.md` is now only what is left to do. Everything durable about how the tool is built — system
  shape, data model, the write pipeline and its ordering, validation, invariants, repo layout, verification
  strategy — moved to the new [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md). The old plan had drifted into
  contradicting itself: it still described the tool as P1, claimed nothing had ever been applied to a live
  station two sections after recording the first live apply, listed on-air control and pruning as non-goals
  after both shipped, and named a `tools/schema.py` that does not exist. Open questions now have a single
  home in PLAN, and the decision log points at it instead of keeping a second copy to fall out of date.
- [`docs/public-readiness.md`](docs/public-readiness.md) is now a record of the completed launch
  rather than a pre-flight checklist: the state at publication, the settings to re-verify, and the
  lesson that a public repository exposes **every branch**, so the leak sweep has to cover remote
  refs and not just `main`.

### Fixed

- `.env.example` documents `SUBWAVE_CONTAINER`, which the config loader has read and every tier-2
  `docker exec` has used since early on. An install whose controller container is not named
  `sub-wave-controller` could not discover the override, so tier-2 reads failed against a container
  that was not there. A unit test now pins `.env.example` and `Config.KEYS` to the same key set in
  both directions, so they cannot drift again. `ANTHROPIC_API_KEY` is documented as an
  environment-only variable: it is not a `SUBWAVE_*` key and a value in `.env` does nothing.

## [1.0.0] — 2026-10-31

The first public release. A toolkit for running a **SUB/WAVE** radio station from an agent
session: author the station's character, read what is actually live, and push reviewed changes.

### Added

- **Two capability tiers, always announced.** Tier 1 needs only the station's base URL and admin
  credentials; tier 2 adds `ssh` and `docker exec` for full fidelity. Every command prints the
  tier it is running at and what it could not read.
- **`status`** — tier, station, what is on air, and whether the repo matches the live station.
- **`pull`** — captures the live station into `instance/` with every secret replaced by
  `__REDACTED__`, and records `capture.lossy` when a tier-1 read cannot see whole objects.
- **`diff`** — drift between the repo and the live station, by persona, show and grid cell.
- **`validate`** — checks `instance/` (or `--dir` any station) before applying. Unknown fields
  are warnings, missing fields are errors.
- **`apply`** — dry run by default; `--yes` performs the writes. Validates first, refuses a lossy
  capture or a payload still holding `__REDACTED__`, takes a backup, then re-reads the station and
  fails loudly if a field did not land.
- **`apply --prune`** — the only destructive operation, opt-in and dry by default. Refuses to
  delete a show that occupies grid cells or a persona that hosts a show (unless
  `--force-prune`), and hard-refuses the active persona, the last persona and the last show.
- **`backup` / `restore`** — config and assets outside the repo, including `schedule.json` and
  `blocklist.json`, which the station's own export omits. Writes a `RESTORE.md` saying where each
  file goes back.
- **`character`** — scaffold and edit the character layer: `init --from demo`, `new-persona`,
  `new-show`, `add-to-grid`, and `edit-persona` / `edit-show`, which change only the fields you
  name and refuse an unknown field or wrong type rather than coercing it.
- **`blocklist`** — author bans and rules locally with no network, keyed by a slug→uuid lockfile so
  an apply never mints a duplicate rule.
- **`skills`** — author the station's own DJ segments (frontmatter + prompt) without touching the
  image's built-ins.
- **`onair`** — live control over the station's MCP server, kept strictly separate from config.
  Reads are free; every air-changing verb needs `--yes`, and `skip` additionally needs
  `--expect-id` or `--any-track`.
- **Offline test suite** — `tests/mock_station.py` runs a mock controller in-process on loopback,
  so the suite needs no station, no network and no credentials. `examples/demo/` is a committed
  fictional station in the same shape as a real `instance/`.

### Security

- Initial security policy published ([`SECURITY.md`](SECURITY.md)): threat model, controls, and
  plainly stated accepted risks.
- `scripts/check-secrets.sh` blocks live credentials from entering a commit, as a pre-commit hook
  and as a CI job.
- Secret paths are redacted on the way in and named — never printed — by verification.

### Documentation

- [`AGENTS.md`](AGENTS.md) — the operating contract for an agent working the repo.
- [`docs/PLAN.md`](docs/PLAN.md) — what is left to do; [`docs/decision-log.md`](docs/decision-log.md)
  — why each choice was made; [`docs/applied.md`](docs/applied.md) — the on-air audit trail.
- [`docs/public-readiness.md`](docs/public-readiness.md) — the checklist for publishing this repo.

[Unreleased]: https://github.com/niels-emmer/runsheet/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/niels-emmer/runsheet/releases/tag/v1.0.0
