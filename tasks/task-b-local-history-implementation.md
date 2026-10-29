# Task B local history implementation — 2026-10-29

PR15 merge verified at b62243f; clean worktree switched to PR16 branch
codex/task-b-cbs-priority and merged fetched origin/main (b31ee95). The owner
explicitly requests implementation on this branch. No new PR or merge authorized.

## Concrete increment

Implement the independent B4/B5a local editor from workflow28. Keep B5b vehicle
execution as a subsequent source-backed increment, then CBS read/write before
coding per D-58. Existing aggregate tasks remain open for remaining branches.

1. app/history_files.py: strict bounded version1 JSON, structural validation,
   lossless same-version unknown fields, semantic conflicts, exact model adapter,
   durable deterministic atomic export. Coding storage validators stay intact.
2. ui/service_history_page.py: local offline project, explicit import replacement,
   export, fourteen choices, multi-item cards/expansion, local draft edit/removal,
   conflict visibility, uint32 mileage and all sourced field ranges. No car reads,
   standalone erase, guessed send, automatic sorting/replay or DEMO writes.
3. app/history_workspace.py: separate durable local editing state/provenance and
   draft identities; separate offline/liveVIN/DEMO workspaces. Imports cannot grant
   a sent/verified state or authorize a write. Explicit VIN association only.
4. ui/main_window.py: permit history navigation offline, maintain safe file-worker
   ownership through disconnect/shutdown and global mutation lockout.
5. One-off JSON/byte/error/persistence and actual Qt/DEMO visual checks; independent
   Python/Qt review, fixes, full preflight before push. No tests/ directory.

This increment implements local storage/editor behavior. It does not claim
vehicle history execution, CBS, coding or remaining MIL/DoIP branches complete.
MIL lifecycle review runs independently to identify the next concrete sequence.

## Implemented and reviewed

B5a local editor complete: strict JSON interchange and separate durable editing
workspaces, stable draft IDs/import/copy provenance, native numeric fields,
explicit garage flag,14service choices/13sendable items, unchanged unknown fields,
visible semantic conflicts, local editing/removal, explicit VIN association,
bounded25-card pages and full item expansion. No car reads/sends/mock-file saves.
History is accessible offline and during limited unverified connections.
DEMO's supplied short identifier uses demo-unbound, distinct from offline/live.

All local file I/O runs on one retained page-owned worker. Context identity is
rechecked after modal dialogs; pending VIN switches settle current publication
before changing projects. Initial corrupt load blocks implicit editing/overwrite;
explicit reload/import resolves it. A failed publication stops editing until
reload because directory-sync failure can occur after atomic replacement.
MainWindow waits nonblockingly at shutdown; only the page deletes its file worker.
Global vehicle mutation lockout disables local editing/navigation.

The B4 history-operation journal is **not** implemented by editor persistence.
No previous-response/uncertain vehicle outcomes are manufactured. Journal-date
accounting, frozen append/replacement plans, actual execution/prerequisites/
capacity/activation and write workers remain B4/B5b. CBS read/write follows those
before coding. Remaining earlier protocol/source queue branches stay open.

## Verification — executed 2026-10-29

Retained one-off harnesses, logs and visual artifacts:
`/Users/lennon/BMW-Tool/investigations/task-b-local-history-20261029/`.
No tests/ or automated suite was added.

- history-files-check.py: exact unknown-field roundtrip, atomic failed-publication
  preservation,14types/13items, conflicts, malformed/duplicate-key/nonfinite/deep/
  oversized JSON, Unicode, numeric and VIN boundaries; passed.
- task-b-local-history-check.py: actual worker save/load, expanded cards,
  uint32 mileage, pre-1752 date preservation/unknown flags/status,14choices/13items,
  modal workspace switch rejection, duplicate/future/unknown visibility/export,
  compact large extension preservation, VIN isolation and shutdown; passed.
- history-final-independent-review.py: year0001 lossless, corrupt initial load
  stays noneditable, explicit reload recovers, active disk publication plus pending
  switch at shutdown does not spawn a new worker; passed.
- task-b-history-mainwindow-check.py: offline navigation, actual MainWindow cards,
  mutation lockout, disconnect, DEMO isolation/zero car calls,1000-entry project
  renders25cards, close during active file work and corrupt-state protection;
  passed with zero Qt callback exceptions captured by sys.excepthook.
- task-b-history-demo-check.py: actual asynchronous DEMO connection, history
  navigation in demo-unbound, empty local project rather than claimed mock car
  history, clean worker shutdown; passed with zero Qt callback exceptions.
- Themed Qt visual inspection: MainWindow1050x850/900x650, collapsed/expanded
  records, actual DEMO and560x650scrollable edit form. Readable controls, no forced
  window expansion; imported file order preserved. System regional formatting,
  with pt_BR when system locale is C; English control/service labels.
- Independent Python/Qt/data-integrity reviews by history_local_files and
  mil_lifecycle_review found modal reentrancy, calendar clamping, compact-export
  size inconsistency and corruption/shutdown issues; all fixed and rerun. Final
  independent reviews report no blocking findings. Root full-MainWindow check
  additionally caught duplicate worker deletion; single-owner fix rerun cleanly.

Verification corrections: the first widget-count assertion included widgets
queued for deleteLater; the harness now delivers DeferredDelete before counting.
An early shutdown harness exit0 did not imply correctness: Qt slot exceptions
were printed separately, so sys.excepthook collection/assertion was added and the
actual duplicate-deletion defect fixed. Date minimum setter alone was ineffective;
setDateRange was verified in fresh processes for years0001/1000/1600/1752.
The actual DEMO check exposed its7-character fixture ID and prompted explicit
unbound DEMO isolation instead of inventing a VIN or sharing offline state.

Full scripts/preflight.sh passes Ruff check, Ruff format check and mypy over all
37 app/ui/main source files. Local runtime Python3.15.2; Python3.13 target was not
executed. No vehicle traffic, physical lamp/history/CBS observation, mutation,
Windows/package/signing validation or universal BMW support claim.
