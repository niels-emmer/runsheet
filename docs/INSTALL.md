# Installing runsheet

## What you need

An existing **SUB/WAVE** station. The station is the thing that runs as Docker containers on your
server; runsheet is a checkout that talks to it. This repository ships no station code and no image of
the station, and **nothing here runs Docker on your behalf** — it uses ssh and `docker exec` only to
read the station's state files when you give it host access. Its one image is an optional runtime of
runsheet itself, for a host without `python3` — see [the container section of the
README](../README.md#from-a-container-if-you-would-rather-not-install-python).

The tool itself is one Python file with no dependencies, so there is nothing to `pip install`.

## Ask your agent

Any agent that reads `AGENTS.md` can do the whole setup:

> Install runsheet for me from https://github.com/niels-emmer/runsheet. Clone it, read `AGENTS.md`,
> then run `init` against my station. Ask me for the ssh host and the admin username and password, and
> tell me if the station only allows the lighter HTTP tier.

The repository is built for that: `AGENTS.md` is the hub, and the five procedures in `skills/` are
committed as relative symlinks under `.claude/skills/` and `.agents/skills/`, so Claude Code, Codex and
OpenCode discover them without configuration.

## Three steps by hand

```sh
# 1. get the checkout
git clone https://github.com/niels-emmer/runsheet.git
cd runsheet

# 2. point it at your station; with ssh this discovers the container and state dir
python3 scripts/runsheet.py init --host you@your-server \
    --base-url http://127.0.0.1:7700 --admin-user admin --admin-pass 'your-admin-password'

# 3. open your agent in this directory and ask for the station's status
```

`init` does the setup in one step. Given an ssh address it runs the same read-only discovery `status`
does, finds the controller container and its data directory, and writes `SUBWAVE_HOST`,
`SUBWAVE_CONTAINER` and `SUBWAVE_STATE_DIR` into `.env`; the HTTP flags write the station's address and
admin credentials in the same pass. Host access is HTTP **plus** ssh, so keep `--base-url` and the admin
pair even when you pass `--host`. `--station-password` is there too if your listeners need one. There is
no `.env` yet, so `init` starts from `.env.example` for you.

Without ssh, pass just the HTTP settings for the lighter tier:

```sh
python3 scripts/runsheet.py init --base-url http://127.0.0.1:7700 \
    --admin-user admin --admin-pass 'your-admin-password'
```

Either form writes `.env` in one go. If `.env` already holds a station, `init` prints what it would
write and refuses until you add `--force`, and it masks passwords in what it prints. Anything still
missing afterwards is named in a `next` line, including a missing `SUBWAVE_BASE_URL` or admin pair. The
manual route still works if you prefer it: `cp .env.example .env`, fill it in, and run `status` — it
still prints the two host-access lines to paste back.

## How much you get depends on one choice

**With only the web address** you can author a station from scratch and push it — with `apply --yes
--no-backup`, because a backup is the one thing that tier cannot take. You cannot take over the one you
already have: the API trims host and show details, and it cannot hand back your shows or the weekly grid
at all. A web-address-only copy of a live station is marked lossy, and `apply` refuses it rather than
push back seven fields per show and lose the other nineteen.

**Add ssh access** and you get the whole station: full reads, a capture you can edit, and a backup that
can restore the programming.

You do not have to work out the rest yourself. `init --host` discovers the container and the data
directory and writes both to `.env`; if you prefer to paste them yourself, set `SUBWAVE_HOST` and run
`status`, which still prints the two lines to add.

## One credentials file for many checkouts

Working from many checkouts against one station? Keep the credentials in one file outside all of them,
e.g. `~/.config/runsheet/station.env` (same `KEY=VALUE` lines as `.env.example`), and export
`RUNSHEET_ENV_FILE=~/.config/runsheet/station.env`. Every ephemeral worktree then loads its `SUBWAVE_*`
values from that file and needs no `.env` of its own — and `init` writes to that file when the variable
is set, so one command configures the shared file directly. Precedence: variables already exported in
the environment win, then the file named by `RUNSHEET_ENV_FILE`, then `./.env` — and a named file
replaces `./.env` rather than merging with it, so two stations' credentials cannot be mixed. A path that
is set but missing is a configuration error, not a silent fallback.

## No station yet

`character init --from demo` writes a small fictional station into `instance/`, so you can walk the
whole flow — edit, validate, dry run — without one. `--mock` goes further: it runs any station command
against the repository's own in-process mock station, with no network, no ssh and no live config. Each
invocation starts a fresh station, so nothing persists between commands.
