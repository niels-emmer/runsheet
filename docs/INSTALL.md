# Installing runsheet

## What you need

An existing **SUB/WAVE** station. The station is the thing that runs as Docker containers on your
server; runsheet is a checkout that talks to it. This repository ships no station code and no image of
the station, and **nothing here runs Docker on your behalf** — it uses ssh and `docker exec` only to
read the station's state files when you give it host access. Its one image is an optional runtime of
runsheet itself, for a host without `python3` — see [From a
container](#from-a-container-if-you-would-rather-not-install-python).

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

## From a container, if you would rather not install Python

The published image is a **runtime, not an installation**. It brings `python3`, `ssh` and `git`, and runs
the toolkit out of the checkout you mount at `/repo` — so `instance/`, the audit trail and your git
history are the same files they are without Docker. The tag pins the interpreter, not the toolkit: the
code that runs is whatever your checkout holds.

```sh
docker run --rm -v "$PWD:/repo" \
    --env-file .env \
    ghcr.io/niels-emmer/runsheet:1.1.0 status
```

Tags are release tags, so `1.1.0` is the first one that carries this image — `v1.0.0` predates both the
`Dockerfile` and the workflow that publishes it.

Five things behave differently inside a container. Four have a one-flag fix; ownership and ssh are the
exception:

- **`127.0.0.1` is the container, not your machine.** Point `SUBWAVE_BASE_URL` at
  `host.docker.internal` (add `--add-host=host.docker.internal:host-gateway` on Linux), or run with
  `--network host` on Linux.
- **Ownership and ssh are one decision.** A bind mount keeps the host's ownership, so on Linux the
  default uid 10001 can neither write your checkout (`pull` and `apply` fail with EACCES) nor read a `600`
  ssh key. `--user "$(id -u):$(id -g)"` fixes both, except that `ssh` exits 255 with
  `No user exists for uid …` when your uid has no `/etc/passwd` entry. So on Linux run with both: mount
  `-v "$HOME/.ssh:/home/runsheet/.ssh:ro"`, pass `--user "$(id -u):$(id -g)"`, and mount a generated
  passwd file at `/etc/passwd` (below). Docker Desktop maps ownership, so on macOS none of this is needed.
  A host new to the mounted `known_hosts` still fails to verify, so connect once from the host first.
- **Backups go where you mount them.** `-v "$HOME/.runsheet-backups:/backups"` with
  `backup --dir /backups` (or `apply --backup-dir /backups`); otherwise the default is
  `~/.subwave-backups` inside the container and dies with it.
- **A killed container leaves a lock the next one cannot clear.** The advisory write lock records its
  hostname, and every `docker run` is a new host, so a run that died mid-write blocks the next one. Once
  no run is active, delete `instance/.runsheet.lock`. A bind mount rather than a named volume matters here
  too: the lock lives in `instance/`, which has to be writable.
- **`--read-only` is fine, with one catch.** `instance/`, `docs/applied*` and anything else on a mount
  stay writable — the audit entry is written under the mount, not an image layer. What becomes read-only
  is the image's own `HOME` and `/tmp`, so send backups to a mount (`--dir`, above) instead of the
  default.

On Linux with host access, that combination is:

```sh
# The login name is not cosmetic: ssh falls back to it as the remote user when
# SUBWAVE_HOST carries no user part, and a bare host is a supported setting.
printf 'root:x:0:0:root:/root:/bin/sh\n%s:x:%s:%s::/home/runsheet:/bin/sh\n' \
    "$(id -un)" "$(id -u)" "$(id -g)" > "$HOME/.runsheet.passwd"
docker run --rm -v "$PWD:/repo" --user "$(id -u):$(id -g)" \
    -v "$HOME/.runsheet.passwd:/etc/passwd:ro" \
    -v "$HOME/.ssh:/home/runsheet/.ssh:ro" \
    --env-file .env ghcr.io/niels-emmer/runsheet:1.1.0 status
```

Prefer to keep credentials out of `docker inspect`? Mount a shared credentials file and set
`RUNSHEET_ENV_FILE` to it instead of using `--env-file`.

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
