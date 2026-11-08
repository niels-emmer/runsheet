# D2 — Read state files, write the admin API

- **Date:** 2026-10-31
- **Status:** decided-by-orchestrator
- **Decision:** `pull`/`diff` read `settings.json` and `schedule.json` from the host state dir via
  `docker exec`. `apply` writes through the admin HTTP API (`POST /api/settings`, `POST /api/shows`,
  `PUT /api/schedule`).
- **Why:** the read endpoints are presentation views, not the config document — 4 fields per persona, 7 of
  26 per show, and a 19-key UI summary from admin `GET /api/settings`. The documented OpenAPI export has
  no config writes at all.
- **Rejected alternatives:** round-tripping config through the documented API (silently truncates
  personas and shows); the full backup export (~95 MB, library included, no schedule); editing state
  files directly (root-owned, rewritten by the controller).
