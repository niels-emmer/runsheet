# D7 — Tier 2 (host access) is an accepted requirement

- **Date:** 2026-10-31
- **Status:** decided-by-orchestrator
- **Decision:** ssh + `docker exec` is a supported, first-class capability, not a workaround. Tier 1
  remains fully portable, and every command announces which tier it is at.
- **Why:** full-fidelity reads and a complete backup are impossible over HTTP alone (see D9). Accepting
  host access buys correctness; keeping tier 1 keeps the toolkit usable by someone who will not grant it.
- **Rejected alternatives:** HTTP-only (lossy and dishonest about it); requiring host access (kills the
  portable case).
