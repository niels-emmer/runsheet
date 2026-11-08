# D13 — Tier 2 is discovered from a bare ssh host, not interrogated out of the operator

- **Date:** 2026-10-31
- **Status:** decided
- **Decision:** at tier 1, `status` probes the host it is already given. With `SUBWAVE_HOST` set and the
  state dir or container still unknown or wrong, it runs one read-only ssh round trip that lists running
  containers and inspects their mounts, and treats a mount as the state dir **only** when
  `settings.json` already exists inside it. It then prints the two `.env` lines. A mount is never
  inferred from a path pattern, and a wrong container name on the right host is recovered the same way.
  With no `SUBWAVE_HOST` it prints how to supply one and touches nothing.
- **Why:** tier 2 was the real onboarding cliff. Reaching it required knowing the controller container's
  name and the state dir's path *inside that container* — two install-specific facts a newcomer has no
  way to know, and a tool that asks for them in a refusal message is asking the operator to do the
  discovery by hand. Both are readable from the host. Probing is safe (read-only, `BatchMode=yes`, one
  round trip) and it makes "tell me your ssh address" the only thing the human has to know.
- **Rejected alternatives:** a separate `discover` subcommand (a twelfth command and a doc set to keep in
  sync, for something that is exactly the question `status` exists to answer: what tier am I, and what
  would the next one cost); probing on every command (only `status` is the onboarding surface, and a
  probe behind `apply` would add latency and an ssh dependency to a write path); guessing `/var/sub-wave`
  when nothing is found (the failure mode is reading the wrong file and reporting it as the station);
  asking the human to run `docker ps` and paste the output (that is the manual work being removed).
- **Consequences:** `discover_state_dirs` is injectable through `ssh_run`, so `tests/test_onboarding.py`
  covers the parsing, the ordering and every `status` message with no ssh. `character init` now records
  `capture.tier = null` with `source: "authored"`: nothing was read from a station, and claiming a tier
  there contradicted the "announce the tier, never degrade silently" rule.
