# D14 — Docker ships as an optional runtime image, not an install path

- **Date:** 2026-11-08
- **Status:** decided
- **Decision:** publish `ghcr.io/niels-emmer/runsheet` (linux/amd64 and linux/arm64, unprivileged) as a
  **runtime**: it carries `python3`, `ssh` and `git`, and runs `scripts/runsheet.py` out of the checkout
  mounted at `/repo`. The image copies nothing from the repository and holds no `instance/`. The clone
  remains the unit of installation (C2) and the repo remains the source of truth (D1). It is built and
  exercised on every change and published only from a release tag, so `latest` cannot drift from the
  version someone pinned.
- **Why:** the only reason to reach for a container here is that a host has no `python3`, or an agent
  runs in a sandbox where installing one is awkward. A runtime image answers that in a ~105 MB pull
  without touching an invariant: `REPO_ROOT` still resolves to the operator's checkout, so `instance/`,
  the write lock, `docs/applied*` and `git` history are the same files they are without Docker. It also
  gives `mcp-server` a launchable stdio entrypoint for an agent that would rather not shell out.
- **Rejected alternatives:**
  - **Bake the toolkit into the image and give it a data volume.** `INSTANCE_DIR` is `REPO_ROOT/instance`,
    so the image would need its own `instance/`, its own write lock and its own `docs/applied.md` — a
    second config store with no git history, where `apply`'s "verified against the commit that ran it"
    records a commit nobody can inspect. That is the failure D1 and C2 exist to prevent.
  - **A sidecar on the station host that drops the ssh requirement** by mounting the state dir. This is
    real value, but it is a change to the execution model, not packaging: `LocalStateSource` exists and
    would need a config seam and a tier announcement, and giving a container the state dir means giving it
    `settings.json` and every secret in it. It needs a decision revisiting D7 and a security review, so it
    is deferred rather than refused.
  - **Mounting `/var/run/docker.sock`** so `docker exec` needs no ssh. That hands the container
    root-equivalent control of the host daemon — disqualifying for a tool whose whole premise is that a
    write is reviewed before it lands.
- **Consequences:**
  - `.dockerignore` is a security control, not housekeeping. Nothing is copied into the image, but
    `docker build` still uploads the context to the daemon, so a build started from a working checkout
    must not carry a live `.env` or a station's `instance/` into a layer or the build cache. Pinned by
    [`tests/test_docker.py`](../../tests/test_docker.py), which also fails if a `COPY`/`ADD` ever reappears.
  - Unprivileged by default (uid 10001), which couples ownership and tier 2 on a Linux bind mount: a
    mounted checkout keeps the host's ownership, so 10001 can neither write `instance/` (EACCES on `pull`
    and `apply`) nor read a `600` ssh key — and `ssh` refuses to run at all as a uid missing from
    `/etc/passwd` (`No user exists for uid …`, exit 255). The working combination is
    `--user "$(id -u):$(id -g)"` plus a mounted `/etc/passwd` naming that uid and the operator's login
    name — ssh falls back to the login name as the remote user when `SUBWAVE_HOST` carries no user part,
    and a bare host is a supported setting. The README documents that rather than the image hiding it.
    Docker Desktop maps ownership, so the EACCES half is Linux-only.
    Making the image uid-agnostic would mean rewriting `/etc/passwd` at start-up, and that file is
    root-owned: it is a root entrypoint dropping privileges, a larger change than this packaging
    decision.
  - `SUBWAVE_BASE_URL` must not be `127.0.0.1`: inside the container that is the container. The README
    names `host.docker.internal` and `--network host`.
  - Backups need an explicit directory: `backup --dir` and `apply --backup-dir`. `HOME` works too, but a
    Docker *named volume* is created root-owned, so a bind-mounted host directory is the documented form.
  - A read-only root filesystem is compatible: `instance/`, `docs/applied*` and backups are on mounts,
    so nothing the tool writes touches an image layer. Only the image's own `HOME` (the default backup
    location) and `/tmp` become read-only, which is why the README points backups at `--dir`.
  - The advisory write lock records `socket.gethostname()`, and every `docker run` is a new host, so a
    container killed mid-write leaves a lock the next one cannot prove is stale — the same rule as a
    foreign host, deliberately. The README says to delete `instance/.runsheet.lock` once no run is
    active. A persistent container with a fixed `--hostname` narrows the window but does not close it,
    because pid liveness is per pid namespace.
  - One more release artifact to keep in parity, and one more thing a change can break: the image is
    built from the tagged commit and verified in CI (`validate`, `--mock status`, a non-root check, and an
    assertion that `/repo` is empty inside it).

This does not answer PLAN's open question 3 (whether to ship a compose file for a new *station* install):
that is about the station's stack, and this decision is only about running this toolkit.
