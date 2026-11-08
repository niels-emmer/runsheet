# D11 — Edit vocabularies are sourced from upstream, with a forced-value escape

- **Date:** 2026-10-31
- **Status:** decided-by-orchestrator (supersedes the "Vocabularies" paragraph of D10 and its claim
  that `moods` is an enum; D10's edit semantics otherwise stand)
- **Decision:** the edit-time enum sets are copied from upstream SUB/WAVE, not inferred from this repo's
  sample data. Persona: `controller/src/schemas/persona.ts` `PERSONA_FREQUENCIES` (silent, quiet,
  moderate, chatty, aggressive), `PERSONA_SCRIPT_LENGTHS` (one-liner, concise, extended, storyteller),
  `PERSONA_LINK_STYLES` (natural, announce), re-exported by `controller/src/settings/vocab.ts` as
  `FREQUENCIES` / `SCRIPT_LENGTHS` / `LINK_STYLES`. Show: `controller/src/schemas/show.ts`
  `SHOW_ENERGY` (low, medium, high) and `SHOW_VOCALS` (instrumental, vocal; the field also accepts `''`).
  Lists keep the product's ladder order because `controller/src/settings/persona.ts` bumps a persona one
  rung with `FREQUENCIES.indexOf(...)`. `moods` is **not** an enum upstream — `showStringList` validates
  it against the station's own installed `ctx.moodNames` — so it stays a free-form list here. A value
  outside a known set is still refused, and `--force-value` allows an unrecognised value with a loud
  warning, for a station newer than this toolkit.
- **Why:** D10's sets were read off `examples/demo` and the fixture, and were incomplete: they refused
  `frequency=aggressive` and `scriptLength=extended`, both valid live values. A hard rejection on a
  guessed list turns the tool into the thing that is wrong about a correct edit.
- **Rejected alternatives:** widening the lists by guesswork (the same defect, just later); dropping
  rejection entirely (a typo would reach the station); validating `moods` against a fixed list (the mood
  names are install-specific, so a fixed list would block valid moods).
