# D10 — Editing is a field-level set verb, not a whole-object rewrite

- **Date:** 2026-10-31
- **Status:** decided-by-orchestrator
- **Decision:** `character edit-persona <slug> --set FIELD=VALUE` and `character edit-show <slug>
  --set FIELD=VALUE` (repeatable `--set`) change only the named fields of an existing entity. Every
  unnamed field keeps its value **and its JSON position**; `id` is immutable and a rename never changes
  the slug, the file name or the lockfile. Values are typed at edit time: integers reject non-integers,
  booleans accept only `true`/`false`, and enums (`frequency`, `scriptLength`, `linkStyle`, a show's
  `moods`/`energies`) reject anything outside the vocabulary with the allowed set in the message. An
  unknown field is refused with the list of real fields. The command writes the file, re-runs
  `validate_instance()`, and restores the original text if the result would fail, so an edit cannot
  leave an invalid entity behind. It is pure local file editing: no network, no tier.
- **Why:** the common ask is "make host X warmer" or "turn banter on", and a hand-edit is exactly what
  the station's shallow settings merge punishes — a dropped field disappears on apply. A targeted verb
  keeps the edit reviewable as a one-line diff and makes the typo/type failure loud at edit time instead
  of silent at write time. Separate verbs (rather than one generic `set`) keep the per-entity field
  whitelist obvious and mirror `new-persona`/`new-show`.
- **Vocabularies:** the station's full enum is not published in this repo, so the allowed sets are the
  values its own shape uses — scaffold defaults, `examples/demo`, `tests/fixtures/station.json` and the
  values named in `skills/explain-host/SKILL.md`. A value outside them is refused rather than guessed
  at. `validate` itself stays permissive about values (unknown fields are warnings), because a newer
  server may know more than this repo does; only the edit verbs are strict.
- **Rejected alternatives:** read-modify-write through the API (tier 1 reads are trimmed, so it would
  delete unseen fields); a whole-object `--replace-file` flow (same failure mode, and it makes a
  one-dial change unreviewable); accepting unknown fields as a warning (a typo would be ignored and the
  edit would silently do nothing); stringifying integers and guessing booleans from `1`/`yes` (the
  station's merge does not tell you it ignored the value).
