# D4 — `listenerAuth` is self-contained in settings

- **Date:** 2026-10-31
- **Status:** decided-by-orchestrator
- **Decision:** Flipping `privacy.listenerAuth` is a settings change plus one mixer restart. The
  controller writes the Icecast listener-auth file; the next broadcast/mixer restart regenerates the
  Icecast config with per-mount URL auth pointing back at the controller. No `icecast.xml`, compose or
  reverse-proxy edit. `stream.maxListeners` rides the same restart path.
- **Why:** verified against a live station. It means the change is reviewable like any other setting
  instead of being an undocumented host edit.
- **Rejected alternatives:** hand-editing the generated `icecast.xml` (overwritten on restart); changing
  the reverse proxy (it already refuses the listener-auth path).
