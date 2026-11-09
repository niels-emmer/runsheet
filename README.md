# runsheet

[![CI](https://github.com/niels-emmer/runsheet/actions/workflows/ci.yml/badge.svg)](https://github.com/niels-emmer/runsheet/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

![An engineer and a robot DJ sharing a mixing desk in a radio studio](docs/assets/station.png)

runsheet keeps a live SUB/WAVE station's configuration as plain files in a checkout you control, so you
can look after it by talking to your agent instead of clicking through the admin console. Diff it, commit
it, revert it — the station keeps running exactly as before; this changes how its config gets edited,
checked and put back.

## Install it with your agent

Paste this into Claude Code, Codex, OpenCode, or any agent that reads `AGENTS.md`:

> Install runsheet for me from https://github.com/niels-emmer/runsheet. Clone it, read `AGENTS.md`, then
> run `init` against my station. Ask me for the ssh host and the admin username and password.

That is the intended path, and the repo is built to be discoverable that way: `AGENTS.md` is the hub, and
the five procedures in `skills/` are committed as relative symlinks under `.claude/skills/` and
`.agents/skills/`, so all three named agents find them with no setup. There is nothing to install — the
tool is one Python file using only the standard library. If the host has no `python3`, there is an
[optional runtime image](docs/INSTALL.md#from-a-container-if-you-would-rather-not-install-python).

### Or three commands yourself

1. `git clone https://github.com/niels-emmer/runsheet.git && cd runsheet`
2. `python3 scripts/runsheet.py init --host you@your-server --base-url http://127.0.0.1:7700 --admin-user admin --admin-pass 'your-admin-password'`
3. Open your agent in that directory and ask **"what's on air?"**

runsheet does not run Docker: your SUB/WAVE station does, and giving runsheet host access only means it
reads the station's state over ssh. No station yet? `character init --from demo` writes a fictional one.
Full setup — both tiers, one credentials file across many checkouts, the manual `.env` route — lives in
**[docs/INSTALL.md](docs/INSTALL.md)**.

## Why use this instead of the console

- **Nothing goes live unexamined.** `apply` is a dry run by default, prints every change, waits for your
  `--yes`, then reads the station back and fails loudly if a field did not actually land.
- **An agent can do the authoring.** Adding a host, writing their soul, creating a show and filling grid
  cells becomes a conversation instead of a form — with the same diff and confirmation in front of it.
- **Backups that can actually be restored.** The console's export drops the schedule, every show and the
  blocklist; this captures them and writes a note saying where each file goes back.
- **Live control stays separate and deliberate.** Reads, edits and on-air actions are distinct doors, so a
  routine sync can never accidentally skip a track or say something on air.
- **History answers "what changed last Tuesday".** Hosts, shows and bans are plain files, so keep them in
  your own version control and diff, blame or revert — nothing here publishes your station's details.

## What you can ask for

| Say something like | You get |
| --- | --- |
| "What's on air right now?" | the track, the show, the host, and whether the stream is healthy |
| "What changed since last week?" | drift against the live station, by host, show and hour — it changes nothing |
| "Why does `<host>` talk so much?" | their dials and character read, the smallest fix proposed, no guessing |
| "Make `<host>` warmer" | that one setting changed, before and after, nothing sent until you agree |
| "Add a host" / "make me a new show" | a persona or programme scaffolded, then the grid cells it fills |
| "Stop playing `<artist>`" | a station-wide ban, or one that applies only while a show is on air |
| "Back up the station" / "push my files to the station" | a restorable copy, or a diffed, confirmed apply |
| "Say something on air" / "skip this track" | live control, with an explicit `--yes` every time |

The long version — including the one rule that surprises people about seasonal bans — is in
**[docs/USAGE.md](docs/USAGE.md)**.

## A session looks like this

```
You:    add a host
Agent:  Happy to. What is this host like - name, temperament, how they talk?
You:    Ada Vance. Dry, unhurried, notices small things, never oversells a record.
Agent:  Here is the host it built, with a soul in her voice. Before I put her on air,
        which show should she present?
You:    Sunday mornings
Agent:  That fills Sun 07:00-10:00, taking one hour from Late Harbour. Nothing is live yet.
        Say the word and I will push it.
You:    go ahead
Agent:  Applied, then read back from the station: one host, one show, three grid cells confirmed.
```

## Without a checkout

The station serves an MCP endpoint at `/api/mcp` (Streamable HTTP, 21 tools), so an MCP-capable agent can be
pointed straight at it: reads need no credentials, and control tools take the admin username and password.
It has none of the safety properties above — no diff, no dry run, no backup, no read-back, no `--yes` — and
it cannot read or write configuration at all. That is what the checkout, and `apply`, are for.

This repository also has a much smaller MCP server of its own, over stdio:

```sh
python3 scripts/runsheet.py mcp-server     # status, diff, validate; all readOnlyHint
```

Three tools, each a thin wrapper around the command of the same name. There is deliberately no fourth: a
configuration change needs a diff, a dry run and an explicit confirmation, and a `tools/call` has none of
the three.

## What it cannot do yet

- **Avatars and station imaging.** Jingles, sound effects and beds are backed up but not authored here. Use
  the station's admin console for those.
- **Library work.** Tagging, building playlists, searching your collection — that is Navidrome's job.
- **Anything that bypasses the station's review step for a skill's custom script** — the station refuses to
  run one until a person has read and trusted it, and nothing here shortcuts that.

## Safety, short

Nothing is written to your station until you say so, and a backup is taken first (at tier 1 there is no
backup to take, and `apply` refuses unless you pass `--no-backup`). Every write is read back afterwards, so
a change that did not land is reported rather than assumed. Deletions refuse when something still depends
on what you are deleting. The full list of guards, and what each protects against, is in `AGENTS.md`.

## Where to read more

| Doc | Covers |
| --- | --- |
| [AGENTS.md](AGENTS.md) | the operating rules every agent reads, and the full guard list |
| [docs/INSTALL.md](docs/INSTALL.md) | both tiers, credentials, the optional container image, the demo station, `--mock` |
| [docs/USAGE.md](docs/USAGE.md) | every request in the table above, in full |
| [docs/REFERENCE.md](docs/REFERENCE.md) | all commands, flags and the `--json` shapes |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | how it is built and why |
| [docs/PLAN.md](docs/PLAN.md) | what is left to do |
| [docs/decision-log.md](docs/decision-log.md) | why each choice was made, and what was rejected |
| [docs/applied.md](docs/applied.md) | what has aired |
