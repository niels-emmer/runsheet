# D9 — The toolkit must capture the schedule itself

- **Date:** 2026-10-31
- **Status:** decided-by-orchestrator
- **Decision:** `backup` does not delegate to the built-in export. At tier 2 it writes the zip **plus**
  `schedule.json`; at tier 1 it refuses and names what is missing. `pull` captures `schedule.json` from
  the host for the same reason.
- **Why:** the built-in `GET /api/backup/export` is a ~95 MB zip with `settings.json`, `library.db`,
  skills, sfx, jingles, avatars and themes — and **no `schedule.json`**. Personas survive because they
  live in settings.json; every show and the entire grid do not. Full show definitions cannot be read back
  over HTTP at all (`/api/schedule` trims to 7 of 26 fields, there is no `GET /shows`).
- **Rejected alternatives:** treating the API export as "the backup" (silently loses all programming);
  reconstructing shows from the trimmed read (19 fields are simply absent).
