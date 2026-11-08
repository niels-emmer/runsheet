# Skills

A skill here is one directory, `skills/<name>/SKILL.md`: a YAML header with a `name` and a
`description`, then a procedure an agent can follow without re-deriving the station's rules. The
`description` is the matching surface — it says what the skill does **and** the sentences that
should trigger it. The body is procedure, not doctrine: `AGENTS.md` is the authority on tiers, the
config API and safety, and every skill links back to it rather than restating it.

These are agent-agnostic in format and in content: a YAML header with a `description` is the shape every
agent matches on, and nothing here names a station, host, persona or show — the operator's own data stays
in gitignored `instance/`, referred to as `<slug>` and `<persona>`.

**A skill is written once, here.** Each loader scans a directory of its own, so each of the five appears in
two tool-owned directories as a **relative symlink** back to this one:

- `.claude/skills/<name>/SKILL.md` → `../../../skills/<name>/SKILL.md` — Claude Code's project path.
- `.agents/skills/<name>` → `../../skills/<name>` — the skill's **folder**, not the file, which is the form
  Codex's docs describe following; it scans `.agents/skills` from the working directory up to the repo root.

OpenCode reads both of those as project *compatibility* sources, so two directories cover all three agents.
The repo deliberately does not also link them into `.opencode/skills`: OpenCode would then register every id
a third time from the same file, and its docs say to avoid duplicate IDs.

Git records these as symlinks (mode `120000`), not file copies, and a relative target resolves from any
checkout — a plain clone or a linked git worktree — so there is still exactly one `SKILL.md` to edit and
nothing to keep in sync. `tests/test_skill_discovery.py` enforces that rather than asserting it: every tracked
`skills/<name>/SKILL.md` must have both links, in symlink mode, with the exact relative target and a row in
`AGENTS.md`, and a link with no skill behind it fails too.

`AGENTS.md`'s "Which procedure to load" table stays the routing surface for an agent whose loader is neither
of those directories, and for all of them it carries the verb-decides rule and the tier announcement, which
native discovery does not.

## The five

`add-host`, `new-show`, `explain-host`, `tune-host` and `backup`. The trigger sentences — and which verb
decides when a request fits two of them — live in [`AGENTS.md`](../AGENTS.md) under **Which procedure to
load**. Keep them there: a second copy here is a second thing to fall out of date.

## Why diagnosis and change are separate skills

`explain-host` only reads; `tune-host` writes. A host that talks too much has one change at the end of it,
and running the diagnosis first is what stops a station getting two changes at once and no idea which one
helped. `AGENTS.md` carries the routing rule and the tier announcement every skill owes the operator.

## Writing another

Copy the section order: when to use, done-when, preconditions (tier, backup), numbered procedure
with the exact commands, verification, failure modes. Keep it verifiable: if a flag is not in
`scripts/runsheet.py --help` or `AGENTS.md`, it does not go in the skill — say it is planned.

Then wire up discovery, or the skill is invisible to every agent: create `.claude/skills/<name>/` holding a
`SKILL.md` symlink to `../../../skills/<name>/SKILL.md`, create `.agents/skills/<name>` as a **folder** symlink
to `../../skills/<name>`, and add a row to the `AGENTS.md` table. `tests/test_skill_discovery.py` fails until
all three exist.
