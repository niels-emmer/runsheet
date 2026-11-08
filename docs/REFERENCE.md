# Reference

The technical appendix: tiers, commands, flags and the `--json` documents. `--help` is the authority for
any command; this page is the map.

## Two ways to reach a station

The second is worth having.

|  | Web address only | Plus ssh access |
| --- | --- | --- |
| Needs | address + admin password | also ssh and `docker exec` |
| Create / update | author from scratch only, with `--no-backup` | yes |
| Read hosts and shows | trimmed | complete |
| Read the weekly grid | yes | yes |
| Backup | **refused** | complete |

runsheet does not run Docker. The station does; host access means runsheet runs `docker exec` over ssh
to read the state directory inside the controller container (see [INSTALL.md](INSTALL.md)).

## Commands

| Command | What it does | Example |
| --- | --- | --- |
| `init` | write `.env` in one step: discover host access, or record HTTP-only credentials | `init --host you@server` |
| `status` | tier, station, what is on air, drift vs your files (tier 2 only), and the lines that reach host access | `status` |
| `capabilities` | what the current tier can do, and why a verb cannot; `--json` for an orchestrator | `capabilities --json` |
| `pull` | copy the station into `instance/` | `pull --force` |
| `diff` | what differs between your files and the station | `diff` |
| `validate` | check your files before applying | `validate --dir examples/demo` |
| `mcp-server` | the same three reads as MCP tools, for an MCP client | `mcp-server` |
| `apply` | send your files to the station; dry run unless `--yes` | `apply --yes` |
| `backup` | config, assets and schedule, outside the repo | `backup --with-library` |
| `restore` | put a backup back | `restore <dir> --yes` |
| `character` | hosts, shows and the weekly grid | `character new-show <slug> --persona <persona>` |
| `skills` | the station's own DJ segments | `skills new late-shift` |
| `blocklist` | bans and rules | `blocklist block --type artist --id <id>` |
| `onair` | live control | `onair say "Back after this." --yes` |
| `--mock` | run any station command against the in-process mock station: no network, no ssh, no live config | `apply --yes --mock` |

## Flags

`init` takes `--host` for host access, plus `--base-url`, `--admin-user`, `--admin-pass` and
`--station-password` for the station's HTTP side (the HTTP flags work with or without `--host`), and
`--force` to update a populated `.env`. `apply` also takes `--force-now` (write while on air),
`--no-backup`, `--backup-dir`, and `--prune` / `--force-prune` for things on the station but not in your
files. `pull` takes `--allow-lossy` for a partial copy. `--mock` works with every command that talks to a
station and swaps the station for the repository's own mock (`tests/mock_station.py`), started in-process
on loopback as a tier-2 station; it ignores `SUBWAVE_*` and `.env` entirely. Each run starts a fresh
station, so nothing persists between invocations. `backup --dir` writes the copy somewhere other than
`~/.subwave-backups`, and `restore --force-now` restores while the station is on air. `character init`
takes `--from demo|blank` — a placeholder station instead of the demo — and `--force` to replace an
existing `instance/`. `skills edit` changes `--label`, `--cooldown` and `--brief`, and `blocklist rule
add|edit` authors a rule by slug.

The `onair` reads are free: `onair tools`, `onair now`, `onair state`, and `onair list skills|sfx|jingles`.
Every `onair` verb that changes air needs `--yes`: `say` (with `--raw` to say it verbatim, `--over-track`
to talk over the music, and `--sfx` to play an effect first), `segment`, `skip`, `request`, `queue` (with
`--pick N` to take a result other than the top one), `sfx` and `jingle`. `skip` additionally needs
`--expect-id` or `--any-track`.

## `--json`

`status`, `diff` and `validate` accept `--json`, which prints one JSON document on stdout instead of the
formatted report — the same information, for a caller that must not parse prose. The shape is
`{"command": ..., "ok": ..., "payload": {...}}`, and `payload` holds the command's own fields: `status`
reports tier, endpoint, station, on-air state, config counts, repo-vs-live sync, and the tier-2 discovery
result (`tier2.state` is `not-configured`, `probe-failed`, `none-found` or `found`, with candidates and
any host note); `diff` reports the change count plus personas, shows, changed grid days, settings keys,
character, override, blocklist and skills; `validate` reports the directory, errors, warnings, unreadable
input, a combined `issues` list and counts.

`ok` mirrors a zero exit code: for `status` the station API answered, for `diff` no drift was found, and
for `validate` there are no errors and nothing unreadable. A tier-1 `diff` can be `ok: true` on the
readable fields only, so check `payload.trimmed` before treating it as a full match. Exit codes do not
change, so `diff` still exits 1 on drift and `validate` 1 on errors. A failed command still prints a
document — `ok: false`, `payload: null`, and an `error` message — alongside the stderr line, so stdout is
always parseable when `--json` was asked for.

## Two directories are called `skills/`

They are different things:

- `skills/` at the top of the repo — the procedures your agent follows when it works here.
- `instance/skills/` — your station's own DJ segments, the ones that go to air.
