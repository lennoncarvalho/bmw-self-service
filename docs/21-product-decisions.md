# Owner decisions and interview queue

Updated 2026-10-28. Answers define product behavior; proposals remain proposals.
Protocol correctness is determined by reproducible evidence, not preference.

## Confirmed by the owner in this chat

| ID | Decision |
|----|----------|
| D-01 | Core features: ENET connection, vehicle information, DTC read/clear and MIL, service history read/write, easy and advanced coding |
| D-02 | Broad BMW coverage is the goal; reverse engineer supplied reference apps to understand vehicle differences |
| D-03 | Only the owner's car is available for physical validation now; do not label all target vehicles physically validated |
| D-04 | Coding/history write screens save a backup first; diagnostic clearing is explicitly exempt (D-11) |
| D-05 | A custom backup format is acceptable for storage/display; preserve current/intended status and reread the car to verify changes |
| D-06 | Review and correct specifications/tooling first, then review the pending connection PR and current code |
| D-07 | Ask about feature behavior rather than silently adopting assumptions |
| D-08 | After interrupted writes, reconnect, read and compare before offering recovery; do not automatically replay |
| D-09 | Service history supports add, edit, delete and replace; CBS reads/resets are future scope |
| D-10 | No automated tests for now; retain the existing no-suite policy |
| D-11 | No saved backup/report is required before clearing faults |
| D-12 | Once VIN and diagnostic communication are verified, optional read failures do not disconnect the car; explicitly mark unavailable fields and incomplete ECU coverage |
| D-13 | Conditionally prefer retaining the mandatory series picker if it simplifies connection behavior and initial loading across pages; this benefit must be assessed, not assumed |
| D-14 | Identified but unverified ECU/software variants may use supported reads; disable unverified writes until exact definitions and write/readback support exist |
| D-15 | GPL-compatible app distribution is acceptable when evaluating protocol dependencies such as Scapy; the actual app license and release materials still need recording |
| D-16 | First usable release displays faults from all ECUs and offers one Clear All button; no per-ECU or single-code clear action in the UI |
| D-17 | All applicable easy presets from the supplied coding APK/decrypted database are required, not a selected subset; use REA to recover missing mappings/read/write behavior and match the actual model/ECU/software |
| D-18 | Service history read and add are required first; edit/delete/replace from D-09 remain later requirements. Advanced coding is later priority than the minimum easy-coding slice |
| D-19 | Clear All continues on reachable supported ECUs if another ECU is unreachable; report exactly which cleared, failed or were not attempted, then reread supported status |
| D-20 | Block an exact duplicate service-history addition matching date, mileage, dealer and service items. Interrupted-add recovery still rereads/compares and never automatically replays |

## Recovered context, with provenance

Owner says the same previously discussed car is the validation target. The local
demo fixture identifies F48 X1 sDrive20i X-line, model year 2018, NBT. The prior
chat “Plan BMW Service History Tool” includes the owner's explicit NBT
confirmation and successful use of a Windows history writer. “Vehicle service
history summary” repeats year 2018 and production date 2017-03-01; that summary
is secondary context, not a new ECU read. Do not substitute the demo's short VIN
or historical mileage for fresh vehicle identity.

The owner describes ACK interference and an existing proposed fix. Checkout is
`fix/hsfz-ack-handling`, matching open PR #8 at audit start. The index contained
no staged changes at that time; the proposed fix was already committed. Preserve
this work and review it before adding runtime changes.

The first retained session now records macOS arm64, USB Ethernet `en15`,
link-local addressing and HSFZ/VIN success; see
[the session report](23-first-vehicle-session.md). Exact cable/adapter product
identity remains unrecorded. The recovered Windows success establishes a useful
reference workflow, not proof of the same laptop/network setup.

## Backup/write acceptance derived from D-04/D-05

- For coding/history writes, save original car state durably first. Fault
  clearing has an explicit no-report exception (D-11). Include schema/app
  version, VIN, ECU identity/software, raw data where needed, decoded display
  values and integrity checks. A UI-value manifest alone is not a raw backup.
- Keep baseline, intended state and observed readback separately, linked by an
  operation ID. Persist outcomes including partial failure and uncertainty.
- Compare readback against the intended changes before reporting success. A
  transport ACK, `sendall()` or positive UDS response alone is insufficient.
- Recovery can promise only what the saved state and verified encoder support.
  A DTC-clear report cannot restore cleared memory/readiness. Exact file schema,
  retention, import/export, encryption and recovery UX remain to be designed.

## Resolved follow-up

The owner selected reread/compare before recovery, full history editing, no tests
for now and no saved report for fault clearing. CBS is explicitly future scope:
see [the future REA task](../tasks/future-cbs-research.md).

Clear scope is resolved by D-16/D-19: one Clear All action with per-ECU
outcomes, not per-ECU clear buttons. Exact MIL presentation remains to specify;
do not promise clearing eliminates an active fault or keeps the lamp off.

## Connection follow-up resolved on 2026-10-28

Keep the connection when identity and diagnostic communication work but optional
reads fail. Show each unavailable field and incomplete ECU coverage explicitly;
do not replace missing data with guessed values or present a partial scan as clean.
Only expose operations whose required data and protocol support are established.

The owner selected the mandatory series picker **only if it simplifies behavior
and initial loading for all pages**. This is a conditional preference, not an
unconditional UI decision or approval of automatic discovery. During the PR/design
review, assess the picker's concrete effect on connection and page initialization.
If it provides no simplification, bring that finding back before redesigning the
flow. Series selection remains a hint; it cannot prove transport or ECU support.

An identified but unverified ECU/software variant does not require rejecting the
entire vehicle. Allow evidenced read operations and disable unverified writes
with an explicit reason. This does not authorize guessed read requests, routine
calls labeled as reads, or writes based on the selected series alone.

## Next interview rounds

Ask a few related questions at a time and record answers before implementation.

| Area | Concrete behavior to settle |
|------|-----------------------------|
| Release coverage | Wording and capability display for supported reads and disabled unverified writes (D-14) |
| Connection | Assess conditional picker preference (D-13); multiple cars; identity failure; connected/loading/limited status wording |
| Network setup | App-managed address/DHCP with elevation or guided manual setup? |
| Coding | Full applicable source easy catalog required (D-17); define unknown/custom value display and unsupported/authorized software cases; advanced hex later |
| History | Read/add first (D-18), exact duplicates blocked (D-20); chronology/field validation and service-item identity remain to settle; edit/delete/replace later |
| Writes | Multi-ECU partial success; cancel during a write; readback mismatch; restore eligibility; voltage preconditions |
| DTCs | All-ECU fault display and one Clear All (D-16/D-19); preserve source-supported status categories and explicit incomplete scan presentation; no per-ECU/per-code clear UI |
| Data/UI | English/Portuguese/German labels, km/miles, localization, accessibility, keyboard navigation, desired visual redesign |
| Persistence | Backup retention/export/import, per-vehicle isolation, sensitive VIN/raw-log handling, disk-full behavior |
| Release | Windows validation access, signing/notarization, dataset distribution rights, offline updates/search behavior |

“Flawless/production ready” must become measurable acceptance per platform,
vehicle/ECU/software and operation; it cannot be inferred from source-app coverage.
