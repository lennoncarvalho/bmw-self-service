# Capability map — goals and current evidence

Updated 2026-11-04. Single desktop app, one active vehicle connection. This is
not a completed-feature certificate. See [the audit](docs/19-audit-and-readiness.md).
Current work: [Task A](tasks/protocol-library-migration.md) and
[Task B](tasks/rea-protocol-recovery.md); acceptance in
[spec 26](docs/26-feature-readiness-spec.md), source answers in
[doc 27](docs/27-rea-source-guide.md).

| Capability | Intended behavior | Current evidence / blocker |
|------------|-------------------|----------------------------|
| Connection | ENET discovery, correlated identity and inventory | Implemented HSFZ owner and identification; current milestone is ISTA 4.29 (D-60). Source support and physical observations remain separate |
| Vehicle information | Identity, inventory, mileage/voltage/FA and supported values | Source-based reads implemented; odometer/measurements still use app decoders rather than STATUS jobs |
| Diagnostics | All applicable ECU faults and one Clear All | Job-backed FS_/IS_ paths with labelled app fallbacks and per-memory coverage; detail/text reconciliation and VM gaps remain |
| Service history | Local JSON/cards, ADD-only append and explicit replacement | Editor, journals and mode-specific workers implemented; prior car history unavailable, no reader or automatic replay; physical write validation not established here |
| CBS | Reads and confirmed resets before coding | Source-current job-backed read/reset includes CBS7.0 and acknowledged DSC_25 extra sequencing; ownership follows source service workflows |
| Easy coding | Applicable source-defined presets with current values and checked writes | Generated plain catalogue, source-compatible layout selection, actual values, composition/signatures/authorization, checked writes and restore implemented; missing semantic mappings and newer formats remain explicit |
| Advanced coding | Later priority after easy coding | No live editing/write completion claimed |
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
