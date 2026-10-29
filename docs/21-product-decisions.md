# Owner decisions and development authority

Updated 2026-10-29 after the Task B requirements interview. Owner decisions
control behavior; reproducible source/vehicle evidence controls protocol facts.
The current milestone is working personal use from Python source on macOS.
[Spec 26](26-feature-readiness-spec.md) is the consolidated functional contract;
[REA investigations](../tasks/rea-protocol-recovery-investigations.md) own the
remaining factual questions. No unanswered product question from this interview
blocks starting those investigations or planning implementation.

## Decisions

D-01–D-20 originated before this interview; D-21–D-49 were answered on
2026-10-29. Rows explicitly marked superseded retain their historical identity.

| ID | Current decision / historical disposition |
|----|-------------------------------------------|
| D-01 | Core features: ENET connection, vehicle information, DTC read/clear and MIL, service history read/write, easy and advanced coding |
| D-02 | Broad BMW coverage is the goal; reverse engineer supplied reference apps to understand vehicle differences |
| D-03 | Only the owner's car is available for physical validation now; do not label all target vehicles physically validated |
| D-04 | Coding/history write screens save a backup first; diagnostic clearing is explicitly exempt (D-11) |
| D-05 | A custom backup format is acceptable; preserve original/intended/observed state. D-29 supersedes unconditional immediate readback. |
| D-06 | Review and correct specifications/tooling first, then review the pending connection PR and current code |
| D-07 | Ask about feature behavior rather than silently adopting assumptions |
| D-08 | After interrupted writes, reconnect/reidentify and reread/compare when meaningful before user-selected recovery; apply any evidenced cycle requirement first (D-29). Never automatically replay. |
| D-09 | Service history supports add, edit, delete and replace; CBS reads/resets are future scope |
| D-10 | No automated tests for now; retain the existing no-suite policy |
| D-11 | No saved backup/report is required before clearing faults |
| D-12 | Once VIN and diagnostic communication are verified, optional read failures do not disconnect the car; explicitly mark unavailable fields and incomplete ECU coverage |
| D-13 | Conditionally prefer retaining the mandatory series picker if it simplifies connection behavior and initial loading across pages; this benefit must be assessed, not assumed |
| D-14 | Allow source-supported reads on identified variants. Writes require exact definitions and evidenced encoding/application completion semantics; D-29 permits cycle-aware response-confirmed completion. |
| D-15 | GPL-compatible app distribution is acceptable when evaluating protocol dependencies such as Scapy; the actual app license and release materials still need recording |
| D-16 | First usable release displays faults from all ECUs and offers one Clear All button; no per-ECU or single-code clear action in the UI |
| D-17 | All applicable easy presets from the supplied coding APK/decrypted database are required, not a selected subset; use REA to recover missing mappings/read/write behavior and match the actual model/ECU/software |
| D-18 | Service history read and add are required first; edit/delete/replace from D-09 remain later requirements. Advanced coding is later priority than the minimum easy-coding slice |
| D-19 | Clear All continues on reachable supported ECUs if another ECU is unreachable; report exactly which cleared, failed or were not attempted, then reread supported status |
| D-20 | Original exact-duplicate rule is strengthened by D-35: block every new history entry on a date already present. Interrupted adds never automatically replay. |
| D-21 | If multiple vehicles respond on the selected interface, refuse connection until only one remains. Do not choose the first response or offer a vehicle chooser. |
| D-22 | If the gateway responds but VIN cannot be verified, offer limited troubleshooting with connection details/logs; vehicle-dependent operations remain disabled. |
| D-23 | Avoid displaying partial data and filling it in later. Prefer independent page loading if feasible; publish each page's initial result together. One global loading state is an acceptable fallback. |
| D-24 | Normal connection should match the reference experience: select chassis type and Ethernet adapter without manual configuration. App-assisted network setup is conditionally authorized if investigation establishes that it is beneficial and straightforward to implement. |
| D-25 | Display emissions MIL On / Off / Unavailable separately from fault count, using a verified MIL read. After Clear All show the newly observed status even if it remains On. |
| D-26 | Clear All remains available for identified, supported ECUs when scan coverage is incomplete; confirmation explicitly names coverage gaps. |
| D-27 | Advanced coding continues with subsequent ECUs after a definite ECU-local write rejection on a healthy connection. Easy coding stops and reverts all changes in the operation on failure. Advanced mode remains later scope. |
| D-28 | No user-facing Cancel during a write. The user commits definitively after warning/confirmation and accepts responsibility for keeping both vehicle and host device sufficiently powered throughout the operation. |
| D-29 | Some changes may need a full ignition off/on cycle or a new connection before meaningful readback. Investigate per-operation behavior rather than requiring immediate readback universally. Where readback cannot yet be meaningful, checked write-operation responses with user instructions/warnings may be sufficient for completion; do not initiate rollback merely because the same-cycle value has not updated. |
| D-30 | During writes block app actions and normal closing wherever possible, and warn the user beforehand. The user accepts responsibility for adequate power and external interruptions. Explain the actual outcome if an event outside app control interrupts the operation. |
| D-31 | Power acknowledgement policy: block known insufficient power; when reliable readings are unavailable, warn and require confirmation of adequate vehicle/device power. Recover actual applicable limits/checks from evidence. |
| D-32 | Use the simplest method supported by the car for adding history, including whole-list replacement if needed, provided all previous history is preserved and a complete backup is saved first. Native append is not required. |
| D-33 | The date picker must not permit future dates; application validation must reject such a write, including non-UI input paths. This is an app rule, not evidence that an ECU rejects future dates. |
| D-34 | Allow independent garages/owner maintenance and free dealer/garage input, subject to source-evidenced encoding/field limits; do not fabricate official dealer identity. |
| D-35 | Reject any new entry on a date already present in the vehicle history, regardless of mileage/dealer/items. No same-day near-duplicate confirmation exception. This strengthens D-20 for new additions; preserve existing same-day records. |
| D-36 | Superseded by D-39: initial request to block above-current mileage was withdrawn in favor of user-entered mileage without an odometer read. |
| D-37 | Allow backdated entries even if their mileage conflicts with surrounding history; the owner may be recording forgotten maintenance. Do not enforce monotonic mileage across entries. |
| D-38 | Allow multiple service items in one dated history entry, matching supported headunit item identities/encoding. |
| D-39 | Supersedes D-36 and the pending missing-odometer question: do not read current odometer to validate history additions. Write user-entered mileage, with user accountability. Do not block against current odometer or require manual current-mileage confirmation. Source-format numeric/unit/range validation still applies. |
| D-40 | Display an existing value outside preset options as Custom. Preserve it by default, including its original raw bytes in the backup; do not normalize/overwrite it merely because it is not a preset. The owner notes it may already work in the car. |
| D-41 | Keep all backups without automatic pruning; allow users to delete them. No special prohibition on deleting unresolved-operation backups was approved. Explain loss of backup/recovery material on deletion; operation code must still require durable baseline/intent before a new write. |
| D-42 | Support backup export/import between computers. Check vehicle/ECU/software compatibility before restoration; import alone never mutates the vehicle. |
| D-43 | Translate all user-facing content to English for the first release. Portuguese comes later. This includes diagnostic/coding/history labels and descriptions, not just app controls. German is not an approved normal-display fallback. |
| D-44 | Detect system format/region where practical. Fallback is Brazilian Portuguese regional formatting and kilometres. Implementation interpretation: interface text remains English under D-43; regional settings govern dates/numbers and distance-unit defaults. |
| D-45 | Use ordinary, unencrypted backup files with the simplest practical read/write format. No password/export-encryption feature required. |
| D-46 | Do not mask vehicle identifiers in diagnostic logs/exports. Retain complete diagnostic records, including VIN; no automatic export redaction. |
| D-47 | The current milestone is functional personal use on the owner’s car. Real features must work as intended; research documents, DEMO flows and static gates alone do not satisfy acceptance. |
| D-48 | Focus current implementation and owner validation on macOS running the Python app from source. The owner has Windows, but Windows/Intel-Mac validation and packaged release closure are later work, not current completion gates. |
| D-49 | Signing, notarization and application packaging are not required for this milestone. Prioritize a working source application. |

## Precedence and implementation interpretation

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
- D-32 allows internal read/merge/whole-list rewrite for add; it does not enable
  user-facing editing/deletion/replacement. Preserve existing records and unknown
  fields, including any same-day records already on the vehicle. D-35 blocks new
  same-day entries; never silently shift dates. D-39 removes history’s current-
  odometer dependency, while B-INFO may still display supported mileage reads.
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
DTC/MIL variants, history read/rewrite preservation and item encodings, easy
catalog matching/read/write/restore, power limits and ignition/completion semantics.
See the ordered REA checklist. Schema/file names, friendly labels, transaction
budgets and Qt lifecycle are implementation design within the decisions above.

Retain existing Widgets UI conventions; no redesign is required. English coverage,
locale handling, full logs and simple durable backup files are development tasks.
No automated suite is authorized. New behavior questions discovered through REA
must be recorded specifically, not filled with assumptions or used to reopen
already answered choices. Later advanced coding, history editing/CBS and public
release choices do not block this milestone.
