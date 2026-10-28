# Documentation index and authority

Start with [the readiness audit](19-audit-and-readiness.md),
[protocol corrections](20-protocol-evidence.md), and
[owner decisions](21-product-decisions.md). Updated 2026-10-28.

Approved owner decisions define behavior. Reproducible evidence defines
protocol facts. Earlier “complete,” “verified,” “resolved” and checked tasks
are historical claims unless supported by retained evidence. DEMO data and
static checks do not validate vehicle behavior.

## Original documents reviewed

| Document | Current standing / correction |
|----------|-------------------------------|
| [01 — protocol research](01-bmw-protocol-research.md) | Historical overview; transport-by-series and generic coding flows are hypotheses |
| [02 — coding APK analysis](02-bimmercode-analysis.md) | Historical; absence-of-class-search is not proof of absent assets; E-series paths cannot prove F/G behavior |
| [03 — diagnostics APK analysis](03-bimmerlink-analysis.md) | Historical; inferred JSON/sensor/codecs are not wire contracts |
| [04 — history writer analysis](04-service-writer-analysis.md) | Historical; strings do not prove PRG/job names travel over TCP; local file format still uncertain |
| [05 — protocol reference](05-protocol-reference.md) | Historical synthesis; wrong framing/group constants and unsupported examples superseded by doc 20 |
| [06 — database extraction](06-coding-database-extraction.md) | Useful asset inventory; later decryption supersedes unknown-encryption claims |
| [07 — identification flow](07-vehicle-identification-flow.md) | Conceptual; FA/SVT DIDs/XML/VIN interpretation need independent evidence |
| [08 — encryption](08-encryption-key.md) | Records a 16-byte AES-128 key, not AES-256; no proof of car-side authorization |
| [09 — gap analysis](09-gap-analysis.md) | Historical; green completeness marks and estimates are not acceptance results |
| [10 — HSFZ](10-hsfz-protocol.md) | Corrected transport contract; heartbeat behavior remains partly unresolved |
| [11 — coding data format](11-curated-coding-format.md) | Definition schema reference; sample offsets/masks/block writes need verification |
| [12 — service-history wire](12-service-history-wire-format.md) | Reopened; no verified encoder/read contract |
| [13 — architecture](13-replacement-app-architecture.md) | Historical design/examples; “all gaps resolved” withdrawn |
| [14 — DTC database](14-dtc-database.md) | Corrected counts, threading and diagnostic parsing guidance |
| [15 — stack](15-tech-stack.md) | Corrected declared/observed runtime, network and release status |
| [16 — UI spec](16-ui-spec.md) | Proposed UI; protocol tables, health/success claims and recovery text require correction/owner decisions |
| [17 — UI decisions](17-ui-decisions.md) | Existing Widgets conventions retained; widget scalability and worker examples are not validated |
| [18 — coding translation](18-coding-translation.md) | Historical fix narrative; counts and language quality are not a release validation |

## Root and task documents reviewed

| File | Standing |
|------|----------|
| [AGENTS.md](../AGENTS.md) | Current contributor entry point and required gates |
| [README.md](../README.md) | Honest setup/current status; build examples remain unverified |
| [CAPABILITY-MAP.md](../CAPABILITY-MAP.md) | Target capabilities with evidence limitations |
| [SPEC-INFRASTRUCTURE.md](../SPEC-INFRASTRUCTURE.md) | Current readiness/acceptance contract, not a completion certificate |
| [SESSION-PROMPT.md](../SESSION-PROMPT.md) | Resume current review instead of rebuilding finished modules |
| [requirements.md](../requirements.md) | Historical REA brief; instructions are not active unattended execution authorization |
| [plan](../tasks/plan.md) / [todo](../tasks/todo.md) | Historical infrastructure plan/checklist |
| [feature gaps](../tasks/feature-gaps.md) | Historical contradictory completion claims; audit supersedes status |
| [coding gaps](../tasks/coding-database-gaps.md) | Historical implementation claims; actual write/backup blockers in audit |
| [audit plan](../tasks/audit-plan.md) | Scope and verification for this cleanup |

## Local reference trees

At audit start there were 50 additional Markdown files under ignored
`ediabasx/` and `BimmerDaten/` (excluding dependencies). They were inventoried and
screened for scope/contradictions, with focused reading of transport and PRG
references. They are third-party/reference material, not application specs or
freshly certified implementations. Dependency READMEs under `node_modules/`,
venvs, caches and `.git` are excluded from the project-document audit.

Do not edit ignored reference checkouts to fix our documentation. The inventory
is in [reference provenance](evidence/reference-markdown-inventory.json).
Their own agent instructions apply only when working inside those trees.
