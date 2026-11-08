# D8 — The character layer is pluggable

- **Date:** 2026-10-31
- **Status:** decided-by-orchestrator
- **Decision:** a *character* is the themed bundle that makes a station itself — identity, locale,
  timezone, theme, house rules, persona roster, show briefs and the grid. It lives in
  `instance/character/` as small files, so a different character is a different directory, not a fork of
  the code.
- **Why:** the repo is a toolkit for any station; the theme is a user choice, not a product fact. It also
  keeps themed content (and any IP in it) out of a public repo by construction.
- **Rejected alternatives:** hard-coding one theme; keeping personas and shows inside one monolithic
  settings document (unreviewable diffs).
