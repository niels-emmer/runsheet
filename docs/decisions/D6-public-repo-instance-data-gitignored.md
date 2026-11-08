# D6 — Public repo, instance data gitignored

- **Date:** 2026-10-31
- **Status:** decided-by-orchestrator
- **Decision:** the repository will be public. All instance-specific data and PII live in gitignored
  files (`instance/`, `.env`), with anonymised `.example` equivalents committed. Tracked files carry zero
  station facts.
- **Why:** a public toolkit cannot ship one deployment's hostnames, credentials, roster or themed
  content. Scrub-after-the-fact does not work: git history keeps it.
- **Rejected alternatives:** scrubbing before publishing (history survives); a private repo (the point is
  a toolkit others can clone).
