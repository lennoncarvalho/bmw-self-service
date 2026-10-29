# Task B — remaining source/REA investigations

Created 2026-10-29 after owner decisions D-21–D-49. This is a factual work queue,
not new Evidence or completed analysis. [Spec 26](../docs/26-feature-readiness-spec.md)
owns behavior; [source guide 27](../docs/27-rea-source-guide.md) owns artifact paths,
known entry points and retained tool evidence. The original ordered questions
were created open; dated follow-ups record investigation progress.
Current milestone: functional owner Mac Python-source app, not packaged release.

## Required output per finding

Use the [feature ledger](../docs/evidence/feature-contract-ledger.md). Record
original/member/version/hash, exact method/prototype/job/instruction, tool version,
actual Evidence IDs and portable bundle path/hash. Trace variant/data selection
through complete buffers, final job/application result and decoder. Separate
static examples, simulations, owner reports and observed vehicle traffic. Correct
contradicted specs before implementing. No fabricated IDs or proprietary bundles
in Git; export large/full source evidence locally. Preserve full diagnostic logs
without masking under D-46.

## Ordered questions

### R1 — artifact/extract reconciliation (B1; all contracts)

- [ ] Reconcile relevant existing smali/assets with original APK members and full
  hashes; retain extraction identity. Reuse working Android tooling; recover setup
  only for an actually observed tool blocker. Inspect SHM file type/dependencies
  before selecting native/managed tooling; PRG requires a format-aware interpreter.

Output: inventory/ledger updates and exact next class/job entry points, not a
new claim that feature protocols work because the tool opens an artifact.

### R2 — reference connection and host setup (B2; B-CON)

- [ ] S-01/S-02 connect entry → chassis/interface filtering → discovery/entity →
  HSFZ/DoIP/activation/tester/session selection. Trace source-supported F/G/U/I
  branches; chassis naming alone does not establish transport. Distinguish actual
  Ethernet link/address/route requirements and platform-specific host setup.
- [ ] Determine why owner experience needs no manual setup. Assess whether
  assisted configuration is necessary, beneficial and straightforward under D-24;
  specify scoped owned changes/cleanup rather than blindly installing DHCP.

Output: connection state machine and interface/setup assessment; implement D-21
multiple-vehicle refusal, D-22 troubleshooting and D-23 page-batch loading.

### R3 — ECU inventory, identity and optional fields (B2; B-CON/B-INFO)

- [ ] Follow actual topology source/job/decoder, address width, variant/software
  and definition identity; explain rejected F48 topology request. Recover actual
  mileage/voltage/I-level/FA/model/date paths and unavailable semantics. No fixed
  F000/ASCII/XML or generic DID assumptions; no unknown-address fallback to zero.

Output: exact per-field contracts and source-to-page mapping; history writes
must not depend on a current-odometer check (D-39).

### R4 — diagnostic dataset, all-ECU faults and descriptions (B3a; B-DTC-R)

- [ ] S-01 `j6.h`/`j6.e` encrypted data loaders, FileDecompression and actual
  execution engine; trace ECU inclusion/variant resolution and fault memory/status/
  record/detail paths. Match description keys without silent collision aliases.
- [ ] Inventory English-description gaps and translation provenance (D-43),
  preserving numeric codes and complete coverage states independently of labels.

Output: versioned record/coverage/lookup contracts; source-supported categories,
failed/unsupported/not-attempted counts and complete discovered-target accounting.

### R5 — Clear All and emissions MIL (B3b; B-DTC-W)

- [ ] Trace actual clear targets, prerequisites, final application status and
  post-clear fault reads. Recover a real emissions MIL read separately from DTC
  warning bits. Identify target-local rejection vs stream-invalidating failures.

Output: one confirmed Clear All, named coverage gaps, continued reachable targets,
per-ECU results and On/Off/Unavailable MIL (D-19/D-25/D-26). No saved report/backup.

### R6 — genuine history read, file and headunit representation (B5a; B-HIST-R)

- [ ] S-03 SHM read entry → dependencies → S-04 NBT jobs/interpreter → every send
  buffer and decoder. Trace pagination, unknown fields, date/distance/dealer/items
  and ordering. Reconcile local `.bmwsh` representation with wire representation.
- [ ] Verify the owner-referenced multi-item file example without publishing
  personal contents. NBT first; CIC/EVO/MGU are separate evidenced branches.

Output: complete nonmutating history read contract, raw preservation and item
catalog. An add-like routine or local backup serializer cannot substitute for it.

### R7 — history add or preserving rewrite (B5b; B-HIST-W/B-REC)

- [ ] Verify owner-reported SHM whole-list write behavior, actual job/encoder,
  full-list preservation, capacity/field limits, free dealer representation,
  multiple items, final status, interruption risk and supported restore path.
- [ ] Establish whether native append or full read/merge/rewrite is the simplest
  valid implementation (D-32). Recover date/unit encodings; don't ask owner for bytes.

Output: original+new list preservation, pre-send backup/intent and contract-specific
completion. App blocks future/same-day additions; entered mileage needs no current
odometer check or historical monotonicity (D-33/D-35/D-37/D-39).

### R8 — complete easy catalog and live reads (B6a; B-CODE-R)

- [ ] S-02/S-07 exact ECU/software/CAFD matching → current coded-data reads and
  raw/block/decoded layout. Catalog every stable preset ID, applicability,
  multi-field maps and unknown/Custom states. Decrypted definitions are not live values.

Output: every applicable row accounted for with explicit restriction/unsupported/
unresolved evidence. Preserve existing Custom values; no chosen sample subset.

### R9 — composed coding writes and restoration (B6b; B-CODE-W/B-REC)

- [ ] Trace masks/multi-field/block composition, integrity/order/session/security,
  final result and baseline restore encoding. Identify genuine authorization
  restrictions without guessing keys/bypasses. Establish when old values imply
  actual failure versus delayed activation.

Output: supported write/restore contracts for every enabled easy target, preserving
unrelated data. Established easy failure stops/reverts; advanced continuation is
later scope. Never claim atomic or guaranteed restoration after external loss.

### R10 — completion, ignition cycle and observation (B3/B5/B6 cross-cutting)

- [ ] For each mutation/restore distinguish transport ACK, final application/job
  result, stored-value visibility and user-visible activation. Determine immediate
  read, reconnect, ignition-cycle or unsupported verification independently per
  operation. Recover exact cycle instructions, never generalize one setting.

Output: D-29 response-confirmed/cycle-required/observed-verified semantics and
meaningful mismatch rules. A stored value may be readable before visible
activation; investigate rather than assuming. Do not hold a transaction open
waiting indefinitely for a user cycle or auto-replay an uncertain write.

### R11 — vehicle power and host power visibility (B5/B6)

- [ ] Recover actual source power measurements/preconditions and applicable limits,
  units/scales/unavailable cases. Separately investigate macOS host power reporting
  from platform APIs. No invented voltage or battery-percentage thresholds.

Output: D-31 known-insufficient block and unavailable-reading acknowledgement,
with pre-write warnings/lockout. Source evidence does not replace actual owner
vehicle validation. Ordinary locale/file/Qt design is implementation work, not REA.

## Progress and escalation

R1–R5 are first priority; R6–R11 can progress as their operation chains require.
Do not require the whole catalog research to finish before integrating the first
supported read. Each enabled operation still needs its own complete contract.
If sources cannot answer a question, record bounded searches, exact missing
artifact/version and expected observation before requesting additional material.
Existing REA setup observations are historical; no installation is requested here.

Close an item only with retained evidence and remaining branch limits. The final
owner-operated read/write checks validate the Mac/F48/NBT milestone; source-backed
support elsewhere stays distinct from physical validation. No automated suite.

## R6/R7 additional-source investigation — 2026-10-29

Plan executed: pin/fetch relevant OSS source and verify Git blobs; inventory the
new JAR with REA; statically trace Main/FXML/controller/native boundaries with
javap; compare record/catalogue/result contracts with current PRGs and app;
retain reports and record UI ideas. No app/vehicle execution or automated suite.
See [findings](../docs/evidence/task-b-history-new-sources.md).

- [x] Inspect pinned devttys1/bmw-service-manager and the supplied Java package.
- [x] Distinguish CBS current-service reads, generic result reads and experimental
  probes from a complete headunit history reader. Neither source closes B-HIST-R.
- [x] Recheck conflicting result labels against all four exact original PRGs.
  Keep the existing checked decoder; do not accept missing-status/01asgenericOK.
- [x] Corroborate14service-item IDs/labels and seven-byte dealer field independently.
- [ ] Correct current UI item choices:4is microfilter, not oilfilter; coolant12hex
  and transmission23hex lack evidence. Preserve unknown existing values.
- [ ] Establish ADD-only capacity/order/preservation and activation results on exact
  headunit/software. A no-ERASE code path is not a complete preserving-write proof.
- [ ] Recover complete car read/storage/backup and same-day detection; do not loosen
  current baseline guards based on a manual list or unrelated CBS data.
- [ ] Resolve unsigned-distance and status-label discrepancies per variant using
  primary job/display/capture evidence before changing semantic input/display rules.

Garage suggestions, readable plan/step journal, accurate expandable cards and
strict portable format adapters fit current behavior. Offline QR and CBS cards
are later optional ideas; replay/maps/3D and a browser UI migration are not proposed.
