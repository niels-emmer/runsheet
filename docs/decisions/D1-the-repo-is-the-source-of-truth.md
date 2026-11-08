# D1 — The repo is the source of truth

- **Date:** 2026-10-31
- **Status:** decided-by-orchestrator
- **Decision:** Changes are authored here, reviewed as a diff, then applied with explicit verbs: `pull`
  (live → repo), `diff` (read-only drift), `apply` (repo → live). Nothing auto-applies: no daemon, no
  cron, no post-commit hook that writes to a station.
- **Why:** the station is live and a bad config change is audible. Review has to happen before the write,
  and drift has to be visible without touching anything.
- **Rejected alternatives:** editing the live instance and treating it as authoritative; a scheduled
  auto-sync (drift would go on air unattended).

---

## Open questions (not decided)

Tracked in [`docs/PLAN.md`](PLAN.md#open-questions--not-yet-decided), which is the single home for them.
Do not resolve one in code without recording the decision here.
