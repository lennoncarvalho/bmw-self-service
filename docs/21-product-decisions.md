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

OS/Ethernet-adapter/cable details and a fresh connection log remain unrecorded.
The recovered Windows success establishes a useful reference workflow, not
proof of the same laptop/network setup.

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

Exact MIL behavior and supported DTC-clear scope still need clarification; do not
promise that clearing eliminates an active fault or keeps the lamp off.

## Connection decisions now asked, awaiting answers

- Keep a verified connection with explicitly unavailable optional fields, or fail
  connection if any optional read fails?
- Auto-discover vehicle/transport with manual override, or retain mandatory series
  selection?
- Permit supported read-only diagnostics on an identified unverified variant while
  disabling unsupported writes, or reject that vehicle entirely?

## Next interview rounds

Ask a few related questions at a time and record answers before implementation.

| Area | Concrete behavior to settle |
|------|-----------------------------|
| Release coverage | How should identified but unverified/unsupported variants be shown? Is read-only partial support acceptable? |
| Connection | Auto-detection vs selector hint; multiple cars; partial VIN/ECU failures; connected vs loading vs limited status |
| Network setup | App-managed address/DHCP with elevation or guided manual setup? |
| Coding | Exact supported preset families; unknown current values; advanced hex scope; protected/new signed coding restrictions |
| History | Local headunit only; chronology and duplicate rules; dealer fields; date/km corrections; erase confirmation; notes kept locally or in car |
| Writes | Multi-ECU partial success; cancel during a write; readback mismatch; restore eligibility; voltage preconditions |
| DTCs | Confirmed vs pending/current/history; per-ECU clear; single-code clear only when supported; incomplete scan presentation |
| Data/UI | English/Portuguese/German labels, km/miles, localization, accessibility, keyboard navigation, desired visual redesign |
| Persistence | Backup retention/export/import, per-vehicle isolation, sensitive VIN/raw-log handling, disk-full behavior |
| Release | Windows validation access, signing/notarization, dataset distribution rights, offline updates/search behavior |

“Flawless/production ready” must become measurable acceptance per platform,
vehicle/ECU/software and operation; it cannot be inferred from source-app coverage.
