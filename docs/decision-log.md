# Decision log

One file per decision in [`decisions/`](decisions/), listed below newest first. Each entry:
**Date / Status / Decision / Why / Rejected alternatives.**
Never rewrite an entry; supersede it with a new one and mark the old one `superseded by Dn`.

[`decisions/`](decisions/) is a directory rather than one growing file on purpose: parallel
contributors each add a file, so two branches never both append to the end of the same log. A new
decision is `decisions/D<n>-<slug>.md` plus one row in the table below.

| # | Date | Decision |
| --- | --- | --- |
| [D13](decisions/D13-tier-2-is-discovered-from-a-bare-ssh-host-not-interrogated-out-of-the-operator.md) | 2026-10-31 | Tier 2 is discovered from a bare ssh host, not interrogated out of the operator |
| [D12](decisions/D12-the-container-name-is-configurable-and-env-example-is-kept-in-parity-by-a-test.md) | 2026-10-31 | The container name is configurable, and `.env.example` is kept in parity by a test |
| [D11](decisions/D11-edit-vocabularies-are-sourced-from-upstream-with-a-forced-value-escape.md) | 2026-10-31 | Edit vocabularies are sourced from upstream, with a forced-value escape |
| [D10](decisions/D10-editing-is-a-field-level-set-verb-not-a-whole-object-rewrite.md) | 2026-10-31 | Editing is a field-level set verb, not a whole-object rewrite |
| [D9](decisions/D9-the-toolkit-must-capture-the-schedule-itself.md) | 2026-10-31 | The toolkit must capture the schedule itself |
| [D8](decisions/D8-the-character-layer-is-pluggable.md) | 2026-10-31 | The character layer is pluggable |
| [D7](decisions/D7-tier-2-host-access-is-an-accepted-requirement.md) | 2026-10-31 | Tier 2 (host access) is an accepted requirement |
| [D6](decisions/D6-public-repo-instance-data-gitignored.md) | 2026-10-31 | Public repo, instance data gitignored |
| [D5](decisions/D5-secrets-never-enter-the-repo.md) | 2026-10-31 | Secrets never enter the repo |
| [D4](decisions/D4-listenerauth-is-self-contained-in-settings.md) | 2026-10-31 | `listenerAuth` is self-contained in settings |
| [D3](decisions/D3-mcp-is-control-only.md) | 2026-10-31 | MCP is control-only |
| [D2](decisions/D2-read-state-files-write-the-admin-api.md) | 2026-10-31 | Read state files, write the admin API |
| [D1](decisions/D1-the-repo-is-the-source-of-truth.md) | 2026-10-31 | The repo is the source of truth |

---

## Open questions (not decided)

Tracked in [`docs/PLAN.md`](PLAN.md#open-questions--not-yet-decided), which is the single home for them.
Do not resolve one in code without recording the decision in [`decisions/`](decisions/).
