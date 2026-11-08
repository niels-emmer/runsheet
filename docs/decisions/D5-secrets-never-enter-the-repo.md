# D5 — Secrets never enter the repo

- **Date:** 2026-10-31
- **Status:** decided-by-orchestrator
- **Decision:** Credentials live only in a gitignored `.env` or the OS keychain. `pull` redacts secret
  paths to `"__REDACTED__"` on the way in; `apply` re-hydrates them from the environment at the moment of
  writing. `scripts/check-secrets.sh` plus the pre-commit hook block a leak, and CI runs the same check.
- **Why:** the repo talks to a live broadcast and will be public. A committed credential cannot be
  un-published by a later commit.
- **Rejected alternatives:** encrypting secrets in-repo (the key has to live somewhere, and the blast
  radius is unchanged); relying on `.gitignore` alone (one `git add -f` defeats it).
