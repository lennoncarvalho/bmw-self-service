# Owner decisions and development authority

Updated 2026-10-29 after the Task B requirements interview. Owner decisions
control behavior; reproducible source/vehicle evidence controls protocol facts.
The current milestone is working personal use from Python source on macOS.
[Spec 26](26-feature-readiness-spec.md) is the consolidated functional contract;
[REA investigations](../tasks/rea-protocol-recovery-investigations.md) own the
remaining factual questions. No unanswered product question from this interview
blocks starting those investigations or planning implementation.

## Decisions

D-01–D-20 originated before this interview; D-21–D-55 were answered on
2026-10-29, including the later write-only history/JSON scope correction. Rows explicitly marked superseded retain their historical identity.

| ID | Current decision / historical disposition |
|----|-------------------------------------------|
| D-01 | Core features: ENET connection, vehicle information, DTC read/clear and MIL, local service history JSON/writes under D-50/D-51, easy and advanced coding |
| D-02 | Broad BMW coverage is the goal; reverse engineer supplied reference apps to understand vehicle differences |
| D-03 | Only the owner's car is available for physical validation now; do not label all target vehicles physically validated |
| D-04 | Coding saves complete original ECU data; history preserves local snapshot/intent/results under D-52, not unreadable car history. Diagnostic clearing is exempt (D-11). |
| D-05 | A custom backup format is acceptable; preserve original/intended/observed state. D-29 supersedes unconditional immediate readback. |
| D-06 | Review and correct specifications/tooling first, then review the pending connection PR and current code |
| D-07 | Ask about feature behavior rather than silently adopting assumptions |
| D-08 | After interrupted coding, reidentify/reread/compare when meaningful (cycle first under D-29). History instead uses D-52 journal/manual iDrive inspection and separately confirmed new action. Never automatically replay. |
| D-09 | History scope is now D-51: append and explicit whole-list replacement, with local draft editing. Direct per-record car edit/delete remains later; CBS is promoted by D-58. |
| D-10 | No automated tests for now; retain the existing no-suite policy |
| D-11 | No saved backup/report is required before clearing faults |
| D-12 | Once VIN and diagnostic communication are verified, optional read failures do not disconnect the car; explicitly mark unavailable fields and incomplete ECU coverage |
| D-13 | Conditionally prefer retaining the mandatory series picker if it simplifies connection behavior and initial loading across pages; this benefit must be assessed, not assumed |
| D-14 | Allow source-supported reads on identified variants. Writes require exact definitions and evidenced encoding/application completion semantics; D-29 permits cycle-aware response-confirmed completion. |
| D-15 | GPL-compatible app distribution is acceptable when evaluating protocol dependencies such as Scapy; the actual app license and release materials still need recording |
| D-16 | First usable release displays faults from all ECUs and offers one Clear All button; no per-ECU or single-code clear action in the UI |
| D-17 | All applicable easy presets from the supplied coding APK/decrypted database are required, not a selected subset; use REA to recover missing mappings/read/write behavior and match the actual model/ECU/software |
| D-18 | Superseded for history by D-50/D-51: service history read and add were required first; edit/delete/replace from D-09 remain later requirements. Advanced coding is later priority than the minimum easy-coding slice |
| D-19 | Clear All continues on reachable supported ECUs if another ECU is unreachable; report exactly which cleared, failed or were not attempted, then reread supported status |
| D-20 | D-35/D-53 block new same-day dates against known local/pending records; unseen car dates cannot be checked. Interrupted adds never automatically replay. |
| D-21 | If multiple vehicles respond on the selected interface, refuse connection until only one remains. Do not choose the first response or offer a vehicle chooser. |
| D-22 | If the gateway responds but VIN cannot be verified, offer limited troubleshooting with connection details/logs; vehicle-dependent operations remain disabled. |
| D-23 | Avoid displaying partial data and filling it in later. Prefer independent page loading if feasible; publish each page's initial result together. One global loading state is an acceptable fallback. |
| D-24 | Normal connection should match the reference experience: select chassis type and Ethernet adapter without manual configuration. App-assisted network setup is conditionally authorized if investigation establishes that it is beneficial and straightforward to implement. |
| D-25 | *Superseded by D-59 for the indicator source.* Display MIL On / Off / Unavailable; after Clear All show the newly observed status even if it remains On. |
| D-26 | Clear All remains available for identified, supported ECUs when scan coverage is incomplete; confirmation explicitly names coverage gaps. |
| D-27 | Advanced coding continues with subsequent ECUs after a definite ECU-local write rejection on a healthy connection. Easy coding stops and reverts all changes in the operation on failure. Advanced mode remains later scope. |
| D-28 | No user-facing Cancel during a write. The user commits definitively after warning/confirmation and accepts responsibility for keeping both vehicle and host device sufficiently powered throughout the operation. |
| D-29 | Some changes may need a full ignition off/on cycle or a new connection before meaningful readback. Investigate per-operation behavior rather than requiring immediate readback universally. Where readback cannot yet be meaningful, checked write-operation responses with user instructions/warnings may be sufficient for completion; do not initiate rollback merely because the same-cycle value has not updated. |
| D-30 | During writes block app actions and normal closing wherever possible, and warn the user beforehand. The user accepts responsibility for adequate power and external interruptions. Explain the actual outcome if an event outside app control interrupts the operation. |
| D-31 | Power acknowledgement policy: block known insufficient power; when reliable readings are unavailable, warn and require confirmation of adequate vehicle/device power. Recover actual applicable limits/checks from evidence. |
| D-32 | Superseded for unreadable history backup/preserving-rewrite by D-50–D-52. Original decision: use the simplest method supported by the car for adding history, including whole-list replacement if needed, provided all previous history is preserved and a complete backup is saved first. Native append is not required. |
| D-33 | The date picker must not permit future dates; application validation must reject such a write, including non-UI input paths. This is an app rule, not evidence that an ECU rejects future dates. |
| D-34 | Allow independent garages/owner maintenance and free dealer/garage input, subject to source-evidenced encoding/field limits; do not fabricate official dealer identity. |
| D-35 | D-53 limits same-day enforcement to known local/pending records, regardless of mileage/dealer/items; unseen car dates cannot be checked. No same-day confirmation exception or silent date shifts/merge. Append never requests ERASE or replacement; replacement list uniqueness is checked within that list. |
| D-36 | Superseded by D-39: initial request to block above-current mileage was withdrawn in favor of user-entered mileage without an odometer read. |
| D-37 | Allow backdated entries even if their mileage conflicts with surrounding history; the owner may be recording forgotten maintenance. Do not enforce monotonic mileage across entries. |
| D-38 | Allow multiple service items in one dated history entry, matching supported headunit item identities/encoding. |
| D-39 | Supersedes D-36 and the pending missing-odometer question: do not read current odometer to validate history additions. Write user-entered mileage, with user accountability. Do not block against current odometer or require manual current-mileage confirmation. Source-format numeric/unit/range validation still applies. |
| D-40 | Display an existing value outside preset options as Custom. Preserve it by default, including its original raw bytes in the backup; do not normalize/overwrite it merely because it is not a preset. The owner notes it may already work in the car. |
| D-41 | Keep all backups without automatic pruning; allow users to delete them. No special prohibition on deleting unresolved-operation backups was approved. Explain loss of backup/recovery material on deletion; require a durable coding ECU baseline/intent or history local snapshot/intent/results before a new write. |
| D-42 | Support backup export/import between computers. Check vehicle/ECU/software compatibility before restoration; import alone never mutates the vehicle. |
| D-43 | Translate all user-facing content to English for the first release. Portuguese comes later. This includes diagnostic/coding/history labels and descriptions, not just app controls. German is not an approved normal-display fallback. |
| D-44 | Detect system format/region where practical. Fallback is Brazilian Portuguese regional formatting and kilometres. Implementation interpretation: interface text remains English under D-43; regional settings govern dates/numbers and distance-unit defaults. |
| D-45 | Use ordinary, unencrypted backup files with the simplest practical read/write format. No password/export-encryption feature required. |
| D-46 | Do not mask vehicle identifiers in diagnostic logs/exports. Retain complete diagnostic records, including VIN; no automatic export redaction. |
| D-47 | The current milestone is functional personal use on the owner’s car. Real features must work as intended; research documents, DEMO flows and static gates alone do not satisfy acceptance. |
| D-48 | Focus current implementation and owner validation on macOS running the Python app from source. The owner has Windows, but Windows/Intel-Mac validation and packaged release closure are later work, not current completion gates. |
| D-49 | Signing, notarization and application packaging are not required for this milestone. Prioritize a working source application. |

## History scope correction — 2026-10-29

The owner accepts unavailable headunit history reading for this product and
instructs us to stop pursuing it. This is a scope decision informed by the
[bounded source findings](evidence/task-b-history-new-sources.md), not proof
that every possible BMW access method is impossible. The latest clarification
requires **JSON only**; the earlier proposed legacy-file adapters are withdrawn.

| ID | Current decision / implementation consequence |
|----|-----------------------------------------------|
| D-50 | Remove vehicle history read/readback from Task B requirements and stop reader/probe research. The app manages local records; it cannot retrieve or back up existing car history. Coding reads/backups remain required. |
| D-51 | Support append of one multi-item entry without ERASE, and a separate explicit erase-and-replace workflow writing a user-reviewed local list. No silent replacement fallback, standalone erase action or direct editing/deleting individual car entries in this milestone. Editing a local replacement list is preparation, not car editing. |
| D-52 | History no longer requires a complete vehicle-read baseline or a car-history backup. Persist local project/intent/exact requests and results before/through writes, identify prior vehicle history as unavailable, and warn about that limit. Replacement irreversibly removes entries absent from the supplied list. No guaranteed restore of unknown car records, automatic rollback/retry/resume or readback-based completion. This exception does not relax coding baseline/restore requirements. |
| D-53 | Consequence of D-50 and unchanged date rules: block future writes and same-day additions against known local/pending records; explicitly disclose that unseen car dates cannot be checked. Validate a replacement list for duplicate dates; retain imported conflicts for preview/export and require explicit resolution before sending. Never silently shift dates, drop duplicates or merge them. |
| D-54 | Settle the service selector to the fourteen evidenced types in doc 28. Remove guessed coolant/transmission/oil-filter-as-microfilter choices. No custom service-item identity/free-text type without an evidenced wire field; supported garage text remains free input within its real field limits. |
| D-55 | Multi-item cards and simple versioned JSON import/export are required implementation tasks. No .bmwsh/.tst support or adapters in the product; those formats remain research evidence only. No QR or other format is needed for this milestone. |

[History workflow 28](28-service-history-workflow.md) makes these decisions
concrete. No new product interview is required to remove the obsolete reader
prerequisite; actual encoder/session/capacity/result facts still need evidence.

## Read/write strictness and popular coding — D-65–D-66 (2026-10-30)

- **D-65 — Relaxed reads, strict writes.** Reads may use best-effort decoders
  from available sources (job files, coding data, public documentation) and
  show values with a source label instead of withholding them until fully
  traced. Writes keep the full contract: exact identity/definition match,
  complete backup, confirmation, power acknowledgement, journal, lockout,
  checked completion, readback/restore and no replay.
- **D-67 — Learn-by-diff rejected (2026-10-30).** The owner does not want to
  capture options by trial on the car. The learn-by-diff code was removed. Coding
  needs a ready-made option database for the popular subset/best-sellers; the
  data source is open (see [claude-session-limitations.md](claude-session-limitations.md)
  for options this assistant did not pursue). The recovered write sequence
  ([task-b-coding-write-sequence.md](evidence/task-b-coding-write-sequence.md))
  and the popular-coding list remain valid inputs.
- **D-66 — Popular coding subset (supersedes D-64's deferral; byte-map source
  superseded by D-67).** Following the
  BimmerCode model, implement a small curated set of popular codings that public
  sources confirm exist, only for best-selling models (F48 first, then common
  F/G). Byte maps are learned on the owner's car: snapshot the ECU's complete
  coding, apply the option once with the owner's own BimmerCode, snapshot again
  and store the exact ECU/coding-version/byte/mask/old/new diff as the app's
  own preset (owner-labelled). Presets apply only to the exact coding version
  they were learned on. Other data sources may be added later by the owner.

## ISTA job engine and data — D-60–D-64 (2026-10-30)

Owner interview after the ISTA 4.29.15 analysis
([architecture](evidence/ista-4.29-architecture.md),
[online research](evidence/ista-online-research.md)):

- **D-60 — Target ISTA 4.29.** Support exactly what ISTA 4.29 covers (HSFZ over
  ENET). Newer ISTA/models are a documented later upgrade, not current scope.
- **D-61 — Run ISTA job files.** Diagnostics execute ECU PRG/GRP jobs by name
  (identification, FS_LESEN/FS_LOESCHEN, CBS_DATEN_LESEN/CBS_RESET, STATUS_*),
  using the repo's ediabasx C11 interpreter completed with an HSFZ transport
  and called from Python through a small shim on the existing protocol owner.
  ediabasx is PolyForm Noncommercial: acceptable because of D-63.
- **D-62 — Hybrid data.** A build script converts the owner's F48 (F056) plus
  common F/G platforms (F20/F30/F15/F25, G20/G30/G05/G01) into a compact
  bundled database; every other model falls back to a user-provided ISTA 4.29
  folder (Ecu job files and PSdZ KIS ECU lists) chosen in the app.
- **D-63 — Personal use only.** No public or commercial release is planned.
- **D-64 — Coding deferred** (later revised by D-66). Status note: ISTA 4.29's
  CAFD/fafp files are encrypted and were not used in this increment.
- **Migration.** Hand-written fault, CBS, odometer and measurement code is
  replaced by the equivalent ISTA jobs once the owner's F48 EDIABAS trace
  matches, keeping the app's write safety: confirmation, power acknowledgement,
  durable journal, global lockout, read-only rejection, no replay.
- **Next features after the engine:** fault details, live values from each job
  file's result tables, and selected service functions rebuilt from their job
  calls. An ISTA-style colored ECU tree was not selected.

## Engine fault indicator — D-59 (2026-10-30)

Owner: faults are presented as ISTA does — present/active, or stored but not
confirmed. The check-engine (MIL) indicator is red when the engine ECU has a
present or confirmed fault; engine running or stopped must not change it. The
indicator therefore follows engine fault memory (`19 02 0C` at 0x12/0x13: status
bit 0 present or bit 3 confirmed), green only when every responding engine ECU
was read with neither, grey when not read. The ECU lamp command (4A69/F303,
lit at key-on with the engine off) is no longer read or shown. Fault rows use
present / stored (confirmed) / not confirmed labels.

## Dashboard emphasis — D-56 (2026-10-29)

The owner wants the first connected page to show as much useful supported car
information as possible, particularly a **green/red MIL indicator**. Green means
an actual supported ECU report of MIL Off; red means On; grey with explanatory
text means unavailable/not read/stale, never inferred Off from zero DTCs. Keep
identity/configuration and technical details organized in expandable groups.
Unknown data stays unavailable and optional failures retain the valid connection.
See [dashboard source findings](evidence/task-b-dashboard-read-findings.md).

## Broad support and validation — D-57 (2026-10-29)

Only the owner's vehicle is available for physical testing. Required development
scope remains most source-supported BMW F/G/U/I models over ENET, not an F48/NBT
implementation. Recover selection, discovery, topology, ECU/definition matching,
requests and decoders across supplied source branches. Do not stop at the
owner's variant or make access to other cars a development dependency.

Complete source-derived implementation, independent review, offline byte/error
checks and UI verification without waiting for fleet hardware. Track physical
observations separately; do not claim unobserved vehicles were physically tested.
Missing evidence requires further source investigation, not guessed universal
constants or a permanent unsupported placeholder. Genuine source restrictions
must retain their reason and next investigation where unresolved.

The owner will review/merge PR13 as an incremental delivery. After confirmed
merge, fetch origin/main and create a fresh codex/ branch for continued Task B;
do not start it before merge or reuse the merged branch. This supersedes earlier
instructions to keep PR13 draft until all Task B work is finished. No merge is
authorized for the agent.

## CBS reading and writing priority — D-58 (2026-10-29)

The owner promotes Condition Based Service **reading and writing** into current
Task B scope, due **before both easy and advanced coding**. This supersedes all
older CBS-later/deferred wording, including D-09 and the former future-CBS task.
The existing connection/diagnostics and history order remains; insert CBS after
history execution and before B6a/B6b. Advanced coding remains later than easy
coding, and CBS precedes it as well.

Use the owner's linked [CBS implementation](https://github.com/devttys1/bmw-service-manager/blob/6c0041bb71674ec52d567c4a6360b5469c048173/bmw_service_manager/cbs.py)
as a concrete read/reset porting reference. Recover and implement all applicable
source-supported CBS read/write branches; do not reduce this to a documentation
or read-only feature. Reset is a CBS mutation, distinct from writing headunit
service history. Inspect actual preconditions, exact ECU/software/version,
requests, decoders and application completion before enabling writes. The
reference's uncertainties and observed vehicle scope remain explicit, not
universal validation. This priority change does not authorize a physical reset.

Use [the promoted CBS task](../tasks/future-cbs-research.md) for source anchors,
implementation acceptance and remaining technical facts. No broad product
interview is a prerequisite; resolve technical questions through source recovery.

## Precedence and implementation interpretation

- D-50–D-55 supersede history-read, complete car-history backup, legacy-format
  interchange and deferred-replacement statements in older specs/tasks/skills.
  History journal/local-file preservation is distinct from a coding ECU backup.
- D-29 supersedes unconditional same-session readback requirements in earlier
  specs, plans, AGENTS and skill examples. Record validated application completion
  separately from actual observed-value verification. A transport ACK alone is
  insufficient. REA establishes final job status, stored-value reads, delayed
  activation and ignition/reconnect requirements for each operation.
- Easy mode stops/reverts operation changes after an established failure (D-27),
  using an evidenced restore path. A value read before its required cycle is not
  established failure. Restore failure or external interruption remains explicit;
  do not promise atomicity or replay an uncertain operation. Advanced continuation
  on definite local rejection remains later scope.
- D-23 means initial page results publish together after their batch settles,
  including explicit unavailable/failure/coverage states. Prefer independent page
  loading; global loading is acceptable. This does not require every read to succeed.
- D-24 is conditional authorization to implement beneficial, straightforward
  assisted setup after source/platform investigation. It does not establish DHCP
  need or authorize unscoped host-service cleanup. Chassis remains a hint, not
  transport/ECU proof. No setup or vehicle operation was performed in the interview.
- D-50–D-53 replace D-32's read/merge/rewrite gate: append sends ADD only;
  explicit replacement deletes old entries absent from the reviewed local list.
  Check new dates against known local/pending records; replacement uniqueness is
  within the replacement list, not against old ledger dates being rewritten.
  No unseen-car duplicate check, readback or prior-car backup can be promised.
  D-39 removes history's current-odometer dependency; optional B-INFO is separate.
- D-34 free text respects actual format limits; it does not invent dealer codes.
  D-38 multiple items use the actual source-supported item catalog/encoding.
- D-40 preserves Custom values by default; existing presence is not proof that an
  arbitrary encoder is valid. Changes need explicit supported preset selection.
- D-41 permits explicit deletion, including unresolved-operation backups; do not
  add a permanent prohibition. D-30 active-write lockout still prevents disruptive
  deletion while a write is running. Explain the loss of recovery material.
- D-44 governs regional formatting/unit defaults, not interface translation:
  UI/content is English. Use system region where practical, Brazilian formatting
  and kilometres otherwise. Preserve native units and calendar dates internally.
- D-46 records full diagnostic identifiers. It does not require committing private
  captures, unrelated credentials or proprietary reference bundles to Git.
- D-47–D-49 defer packaged/platform/public-distribution acceptance; existing library
  legal notices stay intact. Public licensing, signing and release distribution
  materials remain future work, not reasons to defer functional source development.

## Known vehicle and source observations

Owner validation target: F48 X1 MY2018 with NBT. The retained session in
[doc 23](23-first-vehicle-session.md) establishes HSFZ/VIN on macOS arm64 with
USB Ethernet `en15`; optional reads failed and DTC coverage was gateway-only.
Do not substitute DEMO VIN/mileage for live identity. Windows access exists,
but the current validation target is macOS source launch.

Owner reports SHM.exe rewrites the whole history and the supplied `.bmwsh`
example contains multi-item entries, matching their car. These are investigation
leads, not retained wire contracts. REA must trace serialization and actual jobs.
Tool availability/smoke evidence in doc 27 is historical capability evidence,
not newly recovered feature support.

## Remaining work rather than pending owner choices

Investigate the actual network flow, complete ECU inventory/optional reads,
DTC/MIL variants, history append/replacement execution/results/capacity and item
encodings (not a reader), easy
catalog matching/read/write/restore, power limits and ignition/completion semantics.
See the ordered REA checklist. Schema/file names, friendly labels, transaction
budgets and Qt lifecycle are implementation design within the decisions above.

Retain existing Widgets UI conventions; no redesign is required. English coverage,
locale handling, full logs and simple durable backup files are development tasks.
No automated suite is authorized. New behavior questions discovered through REA
must be recorded specifically, not filled with assumptions or used to reopen
already answered choices. CBS read/write priority is now governed by D-58.
Later advanced coding, history editing and public release choices do not block this milestone.
