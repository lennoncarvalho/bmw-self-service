# Capability map — goals and current evidence

Updated 2026-11-05. Single desktop app, one active vehicle connection. This is
not a completed-feature certificate. See [the audit](docs/19-audit-and-readiness.md).
Current work: [Task A](tasks/protocol-library-migration.md) and
[Task B](tasks/rea-protocol-recovery.md); acceptance in
[spec 26](docs/26-feature-readiness-spec.md), source answers in
[doc 27](docs/27-rea-source-guide.md).

| Capability | Intended behavior | Current evidence / blocker |
|------------|-------------------|----------------------------|
| Connection | ENET discovery, correlated identity and inventory | Implemented HSFZ owner and identification; current milestone is ISTA 4.29 (D-60). Source support and physical observations remain separate |
| Vehicle information | Identity, inventory, mileage/voltage/FA and supported values | Source-based reads implemented; odometer/measurements still use app decoders rather than STATUS jobs |
| Diagnostics | All applicable ECU faults and one Clear All | Job-backed fault/information reads and clears with per-memory coverage. Live records do not yet include occurrence time/km or environment snapshots; no separate permanent-memory erase |
| Service history | Local JSON/cards, ADD-only append and explicit replacement | Editor, journals and mode-specific workers implemented; prior car history unavailable, no reader or automatic replay; physical write validation not established here |
| CBS | Reads and individual confirmed resets before coding | Connect then explicitly Read service status; HSFZ-only current flow. CBS7.0/DSC_25 supported; eight observational branches still lack reset ownership. Unsupported/ambiguous items stay blocked |
| Easy coding | Applicable source-defined presets with current values and checked writes | Actual group reads, composition/signing and target-ECU backups/restore implemented. Applicability is enforced during preparation but not fully filtered in the list; semantic/layout/key gaps remain. Writes currently HSFZ-only |
| Advanced coding | Postponed from current acceptance | No live editing/write completion claimed |
| Unvalidated safety-ECU coding | Owner willing to postpone | Live Easy does not yet have a blanket exclusion gate; the old blocked list applies to Advanced/DEMO only. Explicit current-scope gating remains work |
| Backups/recovery | Complete coding originals; separate history intent/results | Complete coding baseline/intent and explicit restore implemented; history cannot recover unknown erased entries |
| Demo | Explore UI with canned data | UI simulation, never a live baseline or physical validation |
| Distribution | Personal Mac source use first | D-63 personal use; packages/platform acceptance later. Native runtime and standalone data assets built locally; package acceptance remains separate |

Current status is reconciled in [doc 29](docs/29-source-reuse-continuation.md).
This table describes implementation boundaries, not a fresh end-to-end acceptance
run. Historical source/capture evidence remains in the linked feature records.

Development order: verify current sources/runtime → finish remaining CBS and
diagnostic branches using jobs/data → remaining coding source formats and
semantic mappings, followed by richer details and later advanced editing. Reuse implemented history and source contracts.
Only the owner's F48 is available for physical observations; other vehicles do
not gate source-based implementation. Do not open a PR without owner instruction.


2026-11-05 readiness audit: CBS/history/coding writes have source and offline
verification; the retained owner session establishes no physical CBS reset,
history write or coding write acceptance. History replacement cannot recover
unknown erased car entries. The latest owner capture identifies ENTRYNAV
`63 0F1BE0`, which is included in the twelve history-write contracts.

Offline reanalysis of that captured F48 profile resolves all18 reported coding
identities. Its200 source preset entries comprise172 mapped/applicable,8
applicable but unmapped (ACSM), and20 source-inapplicable. Nine of18 coding ECUs
have named curated roots; other definitions do not establish a named easy
catalogue. These are source-profile counts, not current-car observations or
physical write validation. Retained audit:
`~/BMW-Tool/investigations/easy-coding-audit-20261105/results.json`.
