# D3 — MCP is control-only

- **Date:** 2026-10-31
- **Status:** decided-by-orchestrator — settled, do not re-litigate
- **Decision:** `/api/mcp` exposes 21 tools: reads, listener requests, and on-air control. There are
  **zero** config writers. Personas, shows, schedule and settings go through the admin HTTP API.
- **Why:** verified with `initialize` + `tools/list` against a live endpoint. The published manual
  contradicts itself on the count, so `tools/list` is the only truth.
- **Rejected alternatives:** treating the manual as authoritative; assuming a config surface exists
  because the tool list is long.
