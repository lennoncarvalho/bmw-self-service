# Task F — history reliability and integrated acceptance

Priority: after C–E for consolidated acceptance; fix a discovered shared history/
write-integrity regression when encountered rather than waiting for this task.
Status: planned reconciliation/integration, not a rewrite of completed history.
Apply [the shared C–F workflow](task-c-through-f-roadmap.md).

## Goal and baseline

Demonstrate the actual supported workflows: local JSON creation/editing, one-entry
ADD-only history append, explicit erase-and-replace from a reviewed local list,
and coherent integration with connection, CBS, diagnostics and enabled Easy
Coding. Close source/integration gaps and produce an accurate acceptance matrix.

History editor/workspaces,14 sourced service types,1–13 items per entry,
VIN/provenance checks, durable operation journals and mode-specific writers are
already implemented. Twelve exact headunit profiles have recovered ADD/ERASE
contracts; the owner's captured ENTRYNAV `63 0F1BE0` is included. CICM/RAD12 lack
those jobs in the current source release. Preserve exact identity/software gates
rather than accepting the marketing name “NBT” alone.

Read [workflow28](../docs/28-service-history-workflow.md), corrected doc12,
spec26 history/recovery acceptance, existing local-history/history-write task
records and current source-history contract evidence. **No history reader,
legacy file adapters or automatic replay.** Prior car history stays unknown.

## Source investigation → implementation

- [ ] F1: Reconcile each supported headunit's selector, sessions, ADD/ERASE
  parameters, encoder widths/business statuses, pacing and activation/reset
  completion against actual source orchestration and current PRGs. Reuse the
  existing codecs/jobs/generated contracts; use REA and decrypted data for any
  unresolved branch. Do not design a new wire format or weaken ranges to fit an
  interpreter defect. Trace missing dependency/variant restrictions precisely.
- [ ] F2: Close local-file workflow gaps found in create/edit/import/export,
  multi-item expansion, VIN association and mode/session switching. Imported
  provenance/outcome metadata never grants a live write. Local edits do not
  modify the car; unbound projects remain useful offline. Retain unknown fields,
  conflicts and actual operation outcomes without inventing old-car state.
- [ ] F3: Verify append is exactly one unsent draft with no ERASE; unseen duplicate
  dates/capacity refusals never trigger overwrite. Verify replacement previews a
  nonempty list/order, explicitly warns about unknown erased entries and sends
  one planned ERASE followed by the frozen ADD sequence. No mileage sorting,
  current-odometer gate, standalone erase or imported automatic execution.
- [ ] F4: Correct any durability/completion gaps: save local state/intent/exact
  requests before mutation; persist each send/result, stop on unresolved failure,
  retain/export unsaved in-memory evidence and block destructive UI actions.
  Do not claim a restorable backup of unreadable car history. Response-confirmed
  completion comes from checked final application responses. Record any required
  restart/cycle instructions explicitly; subsequent manual iDrive inspection is
  separate observed verification, never presumed. No fabricated readback,
  automatic rollback, retry or replay.
- [ ] F5: Exercise integrated connection/refresh/foreground loading across CBS,
  diagnostics, history and coding. Verify one owner, no competing mutations,
  visible read-only/unsupported/busy reasons, correct stale-state invalidation,
  worker lifetime/shutdown and coherent reconnect/recovery. Fix concrete
  implementation issues; do not turn acceptance into documentation-only work.

## Offline and owner-car acceptance

- [ ] Reuse/extend actual12-profile source encoder/business-status checks and
  boundary vectors. Inject failures before/after ERASE, each ADD and activation;
  verify immutable local intent, partial outcomes and no replay. Preserve the
  corrected native signed-width behavior and Python history storage contracts.
- [ ] Visual Qt/DEMO checks for file creation/editing, multi-item cards, journals,
  confirmations, irreversible-loss warnings, backdrop/progress, mode switching
  and evidence export. DEMO never qualifies as live history/coding evidence.
- [ ] Independent review, fixes and full preflight. Record implementation/source/
  offline results per feature and exact variant, with the remaining source queue.
- [ ] Prepare an owner-F48 checklist using current identities and fresh live
  readings. Observe connection/topology/vehicle facts, CBS display, DTC coverage
  and actual Easy current values. Where the owner explicitly authorizes an
  appropriate write, record CBS before/result/post-state or required cycle,
  history iDrive visibility after activation, and non-deferred coding/restore
  evidence. Do not deliberately erase history or reset a service merely to
  tick a test box. Do not induce faults for occurrence data.
- [ ] Publish a readiness table separating implemented/source-supported,
  offline-verified, physically observed and unresolved/deferred. Owner-car
  observations do not certify the fleet. If no car session is authorized, finish
  source/integration work and retain only the explicitly physical acceptance
  items as pending; do not label unfinished code “waiting for hardware.”

Exit: the supported history/file workflows and cross-feature behavior are
implemented and reviewed, with truthful evidence and recovery boundaries.
Advanced/safety-ECU coding remains deferred. Only the owner's available vehicle
is used for physical acceptance; no additional vehicle is a delivery dependency.
