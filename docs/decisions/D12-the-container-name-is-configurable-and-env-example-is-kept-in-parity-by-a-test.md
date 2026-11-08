# D12 — The container name is configurable, and `.env.example` is kept in parity by a test

- **Date:** 2026-10-31
- **Status:** decided (supersedes the "Container name" open question; also supersedes the "Do not resolve
  these in code" instruction for that one question only)
- **Decision:** `SUBWAVE_CONTAINER` is a supported config key, documented in `.env.example`, defaulting to
  the image default `sub-wave-controller`. It is what every tier-2 `docker exec` uses. A unit test asserts
  that the keys in `.env.example` and `Config.KEYS` are exactly the same set, in both directions, so the
  two cannot drift again. `ANTHROPIC_API_KEY` is documented as a comment only: it is read from the real
  environment (used to rehydrate a redacted `llm.apiKey` on apply) and is deliberately **not** a
  `SUBWAVE_*` key, because `load_dotenv` reads only `Config.KEYS` and a value in `.env` would silently do
  nothing.
- **Why:** the code had already resolved the open question — the key was in `Config.KEYS` and wired
  through every `docker exec` — while `.env.example` omitted it, so an operator whose container has
  another name could not discover the override and tier-2 reads just failed against a container that was
  not there. The gap was invisible because nothing compared the two lists. The decision log said "do not
  resolve in code"; the honest fix is to finish the decision and record it, not to leave the code and the
  docs disagreeing.
- **Rejected alternatives:** documenting the assumption instead and removing the key (it is already
  implemented and tested, and a renamed container is install-specific, so pretending it is fixed would
  break real installs); leaving the key undocumented (undiscoverable is the same as unsupported for an
  operator); adding `ANTHROPIC_API_KEY` to `Config.KEYS` (the loader would then read it from `.env`,
  quietly widening where a credential may live).
