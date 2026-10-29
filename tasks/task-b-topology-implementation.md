# Task B topology and dashboard increment — 2026-10-29

PR13 was verified merged through the GitHub connector (merged at
2026-10-29T18:01:20Z, merge commit06e8baf). The worktree was clean. After
fetching origin, codex/task-b-topology-selection was created from origin/main
06e8baf; the merged implementation branch is not reused.

## Scope and plan

Follow queue1–3 in task-b-next-development.md. Preserve the single protocol
owner, CarWorker I/O, exact variant matching and settled initial page batches.
Do not alter history/coding storage or enable unevidenced mutations.

1. Reconcile source connection/topology/address selection with app/vehicle.py,
   app/protocol/discovery.py, facade callers and the complete diagnostic catalogue.
   Use REA for APK methods and format-aware parsing for PRGs; retain exact
   hashes/locations and specific unresolved source branches.
2. Implement recovered transport/address/definition selection through existing
   owner APIs; preserve unknown/unreachable announced targets and their reasons.
   Expected files: app/vehicle.py, app/protocol selection integration as evidence
   requires, source reproduction scripts/data and focused evidence records.
3. Expand direct MIL matching only where source tables and complete request/
   response/validity paths support it. Use a reproducible catalogue rather than
   a handpicked engine list. Keep dashboard/Diagnostics shared observations.
4. Reconcile diagnostic and coding read callers with any address changes;
   no byte-address fallback on unresolved DoIP branches. Record full branch/data
   accounting separately from source-derived capability and physical observations.
5. Exercise one-off offline bytes, wrong echoes/lengths/identities, negative and
   timeout/budget cases, plus actual background Qt/DEMO visual checks. No tests/.
6. Independent Python/Qt/protocol review, repairs and full preflight; update
   handoff and remaining queue, commit and push using personal GitHub account,
   then open and attach a new PR only after coding is complete. Never merge.

Source findings can refine this plan before edits. History local JSON/journal,
writer execution and full easy coding/recovery remain subsequent queue items;
this increment does not declare them complete or merely hardware-blocked.

## Host interface correction

Observed local native Qt interface inventory identifies en0 as Wifi, while the
old enX heuristic displayed it as Built-in Ethernet. Replace heuristics with
QNetworkInterface Ethernet type and actual human-readable names across platforms.
Show IPv4 configured/unavailable, never infer carrier/car presence. Keep internal
macOS anpi interfaces excluded; no subprocess, elevation or network mutation.
Remove invented en0/en7 fallback after inventory failure. Source ENET path uses
existing adapter broadcasts; assisted configuration is not required by this trace.
Files: app/connection.py and ui/welcome_page.py. Verify with native inventory,
synthetic non-Ethernet/multiple-IP rows and Qt picker rendering.

## Recovered fallback before implementation

S-01 g0.P/Y → g0$j.a/b → g.b/c uses all distinct UDS catalogue addresses when
3F07 fails, is empty, or an extended scan is requested. This is a recovered
148-address branch from all691UDS rows, not a chassis-specific probe list.
Implement error/empty fallback through existing request owner only while stream
is healthy; retain candidate origin and every identification disposition. Never
call fallback candidates gateway-announced topology or claim full-car coverage.
Use the existing shared30-second inventory task budget including queueing;
remaining candidates are not attempted, no retries after transport ambiguity.
Files additionally affected: app/diagnostics.py, ui/diagnostics_page.py and
ui/vehicle_page.py for honest candidate/coverage display and clear confirmation.
Source paths/counts/Evidence and unresolved DoIP translation are recorded by
the delegated topology investigation before PR publication.
