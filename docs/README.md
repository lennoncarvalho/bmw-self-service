# Documentation index and authority

Start with [the readiness audit](19-audit-and-readiness.md),
[protocol corrections](20-protocol-evidence.md), and
[owner decisions](21-product-decisions.md). Updated 2026-10-28.

Approved owner decisions define behavior. Reproducible evidence defines
protocol facts. Earlier “complete,” “verified,” “resolved” and checked tasks
are historical claims unless supported by retained evidence. DEMO data and
static checks do not validate vehicle behavior.

[Read-only vehicle validation and log collection](22-read-only-validation.md)
describes the current source launch and explicit unavailable page states.

[First retained vehicle session](23-first-vehicle-session.md) establishes two
successful HSFZ/VIN exchanges, rejected optional reads and gateway-only DTC
coverage. [The source-first REA plan](../tasks/rea-protocol-recovery.md) defines
the evidence and implementation sequence to close those gaps.

[Protocol library evaluation](24-protocol-library-evaluation.md) records the
UDS/DoIP/HSFZ reuse recommendation, released-source review and migration gates.

## Current development entry points

| Work | Task | Specification / answers |
|------|------|-------------------------|
| A — migrate protocol libraries | [task A](../tasks/protocol-library-migration.md) | [spec 25](25-library-migration-spec.md), [evaluation 24](24-protocol-library-evaluation.md) |
| B — REA and functional feature recovery | [task B](../tasks/rea-protocol-recovery.md) | [spec 26](26-feature-readiness-spec.md), [source/REA guide 27](27-rea-source-guide.md) |

Start another session with [SESSION-PROMPT.md](../SESSION-PROMPT.md). Task A
has an [implementation plan](../tasks/protocol-library-migration.md) and
[ordered development tasks](../tasks/protocol-library-migration-tasks.md);
code implementation and local review are complete, with remaining physical/platform/release
acceptance recorded in the [verification record](../tasks/protocol-library-migration-verification.md). Task B product decisions are consolidated (2026-10-29);
[remaining REA investigations](../tasks/rea-protocol-recovery-investigations.md)
gate affected operations. Current acceptance is functional Mac Python-source
use on the owner’s car; Windows/packages/signing are deferred.
Task B now has an [implementation plan](../tasks/rea-protocol-recovery-implementation-plan.md)
and [ordered development tasks](../tasks/rea-protocol-recovery-tasks.md), based on
main after Task A PR #12 merged. No B feature contract is closed by that planning.
The first usable slice is connection/vehicle info, all-ECU fault display with
one Clear All action, local JSON history/cards with append and explicit erase-
and-replace, and all applicable easy presets. D-50–D-55 retire history reads and
legacy-format adapters. Direct per-record car editing/deletion, advanced coding
and CBS are later scope. [Workflow28](28-service-history-workflow.md) owns the
consolidated history behavior, storage boundaries and acceptance checks. REA now works for
Android inspection; doc 27 records actual evidence and per-tool limits.

[Dashboard read findings](evidence/task-b-dashboard-read-findings.md) record
D-56's richer overview/MIL priority, source-backed voltage/software/inventory,
real optional sensor definitions and a new exact-variant MIL PRG lead. Static
source evidence is separate from owner-car acceptance; green never follows from
an empty/partial DTC scan.

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
| [12 — service-history wire](12-service-history-wire-format.md) | Recovered ADD codec; execution/results/cycle review pending; reader retired under D-50; workflow28 applies |
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
| [SESSION-PROMPT.md](../SESSION-PROMPT.md) | Current two-task development handoff; source and evidence routes |
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

## Implementation slice — 2026-10-29

REA-backed connection/inventory/diagnostics, exact-identity coding snapshots and
portable backup storage are implemented in `codex/task-b-feature-recovery`.
Task B is **not complete**: local history/append/replacement flows, full preset writes and
restoration, broader MIL and DoIP inventory/address recovery remain open.
The [dashboard implementation](../tasks/dashboard-implementation.md) now includes
a [source-traced MIL decoder](evidence/task-b-mil-read-contract.md) for three
exact engine identities; physical comparison remains pending.
The supplied history utility's native read action is a Pro-only message.

See [recovered contracts](evidence/task-b-recovered-contracts.md) and
[verification/review](../tasks/task-b-implementation-verification.md).
