# Applied changes — on-air audit trail

**Rule: no apply lands on a live station without an entry here.** Append the entry at the time of the
apply, never edit a past one.

One entry per apply, as its own file in [`applied/`](applied/), named
`<YYYY-MM-DD>-<short-slug>.md`. [`applied/`](applied/) is a directory rather than one growing file on
purpose: parallel contributors each add a file, so two branches never end an apply by editing the same
lines and colliding on every rebase.

Each entry: **Date / Commit / What changed / Backup ref / Verified by / Listener check.**
`Backup ref` points at the `settings.json` + `schedule.json` copy taken **outside this repo** immediately
before the apply (they contain secrets), e.g. `~/subwave-backups/2026-11-02T1015Z/`. `Listener check` is
the result of one real listener connect afterwards. `Commit` is the repo revision the tool was run from;
a station-side change has no commit of its own, so it names the revision that produced it, or `—` when
none was recorded.

| Date | Entry |
| --- | --- |
| 2026-10-31 | [houseRules → `settings.djHouseRules`](applied/2026-10-31-house-rules.md) |
