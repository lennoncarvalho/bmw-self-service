# Task B — ordered development tasks

Status: decisions consolidated 2026-10-29; all implementation boxes remain open.
Planning baseline `origin/main` `db3c99f`; current milestone is owner Mac source
functionality (D-47–D-49), with Windows/packages/signing deferred. Follow the [implementation plan](rea-protocol-recovery-implementation-plan.md)
for exact proposed files, timing, state design and decision gates; [spec 26](../docs/26-feature-readiness-spec.md)
defines acceptance. Existing [research roadmap](rea-protocol-recovery.md) and
[source guide](../docs/27-rea-source-guide.md) retain investigation leads. Use
the [REA checklist](rea-protocol-recovery-investigations.md) for remaining facts.

## B1 — reconcile artifacts and establish implementable contracts

- [ ] Recheck relevant originals/member hashes and extraction relationships;
  reuse retained B0 evidence without treating tool smoke as feature evidence.
- [ ] Split the feature ledger by actual transport/ECU/software branches. Record
  unresolved or contradicted legacy claims with their next bounded investigation.
- [ ] Trace connection/inventory and optional-read failures first; export real
  REA records and hashes outside Git, sanitized contract summaries inside Git.
- [ ] Recover history writer execution/results and coding read/write chains; inventory every
  easy preset by stable ID/applicability, including exclusions and unknowns.
- [ ] For each operation publish complete endpoint/session/request/response/error/
  decoder/timing/cancel contracts before implementing it. Correct older specs.

Exit: each next enabled operation has an evidence-backed versioned contract;
remaining feature contracts stay open. B1 evolves across slices, not a demand
that every source question close before the first supported read.

## B2 — actual inventory and vehicle information

Depends: B1 contracts for B-CON/B-INFO; Task A API already merged.
Files: `app/vehicle.py` (new), `app/worker.py`, `app/uds.py`, `ui/main_window.py`,
`ui/vehicle_page.py`, `app/mock_connection.py`; docs 07/20/26.

- [ ] Define typed identity, inventory, capabilities and per-field result states;
  retain full transport addresses and software/definition provenance.
- [ ] Recover F/G/U/I selection branches and actual topology decoder; no fixed
  F000/ASCII record assumption, unknown-to-zero conversion or chassis inference.
- [ ] Integrate inventory through Task A; register identities/codecs on its owner.
- [ ] Replace each fixed optional read only with its recovered endpoint/job/codec;
  explain first-session negatives and false empty/I-level success.
- [ ] Keep connected identity usable after optional failures; distinguish failed,
  unavailable and not-attempted fields and preserve stale-generation protection.
- [ ] Apply D-21 single-vehicle requirement and D-22 limited troubleshooting;
  implement D-23 initial page publication after its batch settles (global loading
  acceptable fallback). Assess D-13 picker benefit.
- [ ] Investigate reference network setup and platform requirements; assess D-24
  benefit/implementation scope before selecting assisted setup or DHCP/elevation.
- [ ] Inspect offline bytes/errors and DEMO states; record owner read-only
  inventory/info acceptance separately from source-supported variant breadth.

Exit: B-CON/B-INFO code and contract trace complete for enabled branches;
physical acceptance remains marked pending until actually observed.

## B2 dashboard enrichment — D-56 / MIL priority

Source/limitations: [dashboard findings](../docs/evidence/task-b-dashboard-read-findings.md).
The dashboard/MIL implementation and offline review are recorded in
[the implementation record](dashboard-implementation.md). The direct MIL codec
is now source-traced for exactly three identities; physical acceptance and
additional configuration/measurement decoders remain pending.

- [ ] Expand the first page from VIN to identified model/configuration when
  supported, valid mileage, integration levels, supply voltage and ECU identities/
  coverage, with inline technical details and source-aware unavailable states.
- [x] Prioritize real engine MIL in the initial overview batch, independent of
  opening Diagnostics: green Off, red On, grey unsupported/not-read/stale plus
  text/icon/timestamp. Never use fault count, the generic DTC warning bit or a
  lamp-actuation command as MIL. Verified nonapplicability is not green Off.
- [ ] Finish exact MIL applicability/endpoint/response/validity from the new
  MEVD172/172Y/1725 ISMIL4A69 PRG lead; independently bind engine variant/software.
  Do not apply it to DME9FF or every BMW. Retain exact positive/negative/sentinel
  handling and owner comparison to iDrive/cluster before physical validation.
- [ ] Recover vehicle/FA identity and actual odometer separately from engineering
  lifetime/regeneration mileage; never fabricate model/build/options from hints.
- [ ] Add supported oil/coolant temperatures, RPM and other useful measurements
  in an expanded optional area only after source-to-decoder validation. Avoid a
  connect-time sweep of thousands of engineering sensors or2C dynamic writes.
- [x] Publish the initial bounded page batch together under D-23; prioritize core
  identity/MIL and account for optional failure/time budget without disconnecting
  a verified car. Background manual refresh must respect write/clear lockout.
- [x] Reread the actual MIL after Clear All; never force green. Clear old VIN/
  disconnected/error observations, keep data age visible, and exercise stale/
  unavailable/On/Off cases offline and visually with exact variant coverage.

CBS due-date/distance remains later scope; no history-read investigation resumes.

## B3a — complete diagnostic reads and coverage

Depends: B2 inventory + B-DTC-R. Files: new `app/diagnostics.py`,
`ui/diagnostics_page.py`, `app/dtc_db.py`; docs 03/14/20 and provenance as needed.

- [ ] Recover inclusion/exclusion, memory/status variants, records/details and
  exact description association; resolve data extraction collisions explicitly.
- [ ] Scan discovered supported ECUs with per-ECU progress/results and a documented
  bounded scan budget; preserve not-attempted/unsupported/failed/cancelled states.
- [ ] Render all source-supported fault categories grouped by ECU; preserve raw
  statuses and coverage. A partial empty scan cannot mean whole-car no faults.
- [ ] Keep read-only SQLite ownership on its worker and use exact variant lookup.
- [ ] Manually inspect mixed success/negative/timeout/cancel cases and DEMO/UI;
  collect owner full-scan observations with gaps explicitly accounted for.

Exit: B-DTC-R trace and full discovered-target accounting, with actual validation
scope recorded; snapshot/status flags never substitute for an emissions MIL.

## B3b — one Clear All and independent post-clear checks

Depends: B3a + B-DTC-W/MIL contracts; D-25/D-26 settle presentation/scope. Files:
`app/diagnostics.py`, `ui/diagnostics_page.py`; docs 14/16/20/26.

- [ ] Recover supported clear targets/prerequisites and MIL read semantics.
- [ ] Replace nested legacy ClearWorker with a planned operation; reject missing
  target identities and remove default-address assumptions.
- [ ] Confirm once, clear reachable supported ECUs, track application response
  separately from reread results; no per-code/per-ECU clear buttons.
- [ ] Continue after ECU-local rejection while stream ownership remains valid;
  on transport closure classify remaining targets and require safe reidentification.
- [ ] Permit clearing identified supported targets with scan gaps named in
  confirmation (D-26); MIL On/Off/Unavailable is separate from count (D-25).
- [ ] Reread faults and supported MIL; show cleared/failed/not-attempted plus
  verified, still-present or uncertain post-clear state. No backup/report step.
- [ ] Verify offline partial/forced-interruption/deadline behavior and read-only policy;
  document agreed owner-operated clear validation separately.

Exit: B-DTC-W success requires post-clear observations; response-only success is
removed. Fault recurrence or unsupported MIL remains visible.

## B4 — durable baseline, intent, readback and recovery foundation

Depends: identity/result design; precedes B5b/B6b. Files: new
`app/operation_store.py`, `ui/backups_page.py`; docs 13/16/26.

- [ ] Finalize versioned schema, storage location, identity matching, integrity,
  atomic publication/durability and platform behavior before implementation.
- [ ] Implement coding immutable baseline, separate intent/readbacks and state events;
  preserve individual target states in aggregate partial/uncertain outcomes.
- [ ] Block coding on incomplete original ECU backup; block history on missing
  local snapshot/intent/journal persistence (not on unavailable car history).
  Corrupt data or persistence failure blocks either write.
- [ ] Define eligible portable exports/imports and legacy-preview-only manifests;
  isolate DEMO/live and per-vehicle data. Retain all backups until explicit user
  deletion (D-41); no automatic pruning. Vehicle compatibility gates restoration,
  not local preview/import (D-42); validate imported schema/integrity; retain full unmasked diagnostic identifiers (D-46).
- [ ] Implement coding recovery reidentification/reread/compare and capability filtering;
  no automatic replay or inferred restore ability.
- [ ] Manually inspect disk-full/permission/interruption/corruption/mismatched
  identity cases and process-restart discovery of pending bundles.

Exit: durable pre-send storage and recovery eligibility verified offline;
Coding restoration still depends on its actual encoder/completion/cycle contract.
History uses a separate local journal and cannot restore unreadable original car
records; see workflow 28 and the B4 extension below.

## B5a — local history project, sourced cards and JSON interchange

Depends: B-HIST-F and D-50/D-54/D-55; no car/read/reader dependency. Files:
app/service_history.py, new app/history_files.py, ui/service_history_page.py;
[workflow 28](../docs/28-service-history-workflow.md) owns the concrete contract.

- [ ] Retire B-HIST-R and remove automatic ServiceHistoryReadWorker/page-load
  calls and exploratory probes. Loading/reconnecting shows local records only;
  empty local files never imply an empty car. No further reader investigation.
- [ ] Centralize all 14 evidenced type IDs/English labels for model/selector/cards;
  remove Oilfilter4/coolant12hex/transmission23hex guesses. No custom item or
  silent engine-oil fallback. Support1–13 items per dated entry and 7 ASCII dealer
  bytes with explicit BMW/independent flag; retain entered mileage/native units.
- [ ] Implement schema_version 1/vin/entries project JSON in app/history_files.py:
  strict structure/types/version/size/duplicate-key/nonfinite checks; offline null
  VIN, explicit association and mismatched-VIN send blocking. No legacy adapters,
  QR or imported execution directives. Retire unused runtime legacy-file API.
- [ ] Preserve structurally valid unknown fields/conflicting records for preview/
  export; clearly block unsupported/future/duplicate replacement data from sending.
  Atomic deterministic export, explicit project/file overwrite and all-or-nothing
  import failure must preserve the current project. Verify portable round-trips.
- [ ] Build expandable multi-item cards using widget children: date/mileage/garage/
  status/chips/origin/outcome summary, each item's status/detail on expansion,
  and clear local draft/imported/previous-response states. All items in one card
  are encoded as one dated record. Local edits/deletes never affect the car.
- [ ] Keep future picker/operation rejection, known-local/pending same-day checks,
  user-entered mileage/backdated conflicts and imported conflict visibility. Append
  accepts an unsent draft only; excluding its own draft ID never excludes an
  accepted/uncertain prior journal date. Replacement validates uniqueness within
  its list, not against old ledger dates that it intentionally rewrites. State
  that unseen car dates cannot be checked; never shift/merge/drop dates silently.
- [ ] Verify empty/offline/unbound/mismatchedVIN/conflict/DEMO/live separation,
  settled page publication, card expansion and zero car I/O during file actions.

Exit: B-HIST-F usable with JSON only,14 sourced choices and multi-item cards;
B-HIST-R retired, no car-history backup/reader promise or dependency.

## B5b — one-entry append and explicit erase-and-replace

Depends: B2 exact headunit identity + B4 history journal + B5a + B-HIST-W
execution/result/cycle contract. Files: app/service_history.py,
app/history_files.py, ui/service_history_page.py, ui/backups_page.py; docs12/28.

- [ ] Build immutable mode-specific request plans. Default append contains one
  new entry/ADD and **no ERASE**. Replacement is a separate explicit action with
  a nonempty complete local write list, exactly one ERASE and ADDs in visible
  frozen order. No capacity-error fallback, automatic mileage sorting or import-
  selected mode. Direct per-record car edit/delete/standalone erase stays out.
- [ ] Retain/review exact source variant/session/address/encoding, ADD/ERASE
  business status and activation/reset semantics. Do not copy source status01as
  generic success or a missing-status shortcut. Resolve remaining field/capacity/
  ordering facts; do not require a history reader or old-car baseline.
- [ ] Confirm mode/VIN/headunit/records/items/count/order/power/definitive write
  and activation expectations. Explain no old-car backup/unseen-date check for
  append; require irreversible-loss acknowledgement for replacement. Unknown
  car history itself is not a write blocker; unmatched encoder/identity is.
- [ ] Save local_before/intent/exact request plan/target/encoder/hash and null
  vehicle_history_before before any send. Journal each step and raw response;
  failed persistence prevents starting. A journal failure after a car step stops
  subsequent mutations and reports known effects/partial uncertainty; never
  continue without durable results. Keep coding baseline validation intact.
- [ ] Use CarWorker/Task A owner;30-second request/five-minute operation absolute
  budgets include queueing/delays/reset. Freeze edits/mode/imports and block
  competing operations/navigation/disconnect/normal close; responsive progress,
  no Cancel. Stop on first failed/uncertain history step with remaining unattempted.
- [ ] Validate echoes, complete reply and variant business/reset completion.
  Record response-confirmed/cycle-required outcomes; show iDrive/ignition-cycle
  instructions without readback or synchronization claims. Accepted entries plus
  failed reset are partial, never falsely “nothing written” or fully successful.
- [ ] On interruption preserve known accepted/rejected/unattempted steps and
  uncertainty. Reidentify and show manual inspection instructions; never replay,
  resume at a guessed index, rollback automatically or promise unknown-history
  restoration. Any recovery replacement is a separately confirmed new operation.
- [ ] Offline/manual checks: append contains no ERASE; replacement count/order,
  invalid/empty/duplicate/future/unknown/VIN inputs; journal/disk failures; lockout,
  status/echo/pending/deadline/reset disconnect/partial outcomes; no hidden retry.
- [ ] Independent review and full gates, then agree concrete owner append/iDrive
  check and explicit replacement procedure. Retain actual identity/traffic/results
  separately from static checks. No automated suite or unrequested car writes.

Exit: B-HIST-W and history B-REC meet workflow 28 without a reader. Local files/
intent/results are preserved; replacement loss limits and physical acceptance
remain honest. Coding's separate baseline/readback/recovery requirements remain.

## B6a — full easy catalog and current coded values

Depends: B2 + B-CODE-R and catalog evidence. Files: new `app/coding.py`,
`app/coding_db.py`, `ui/coding_page.py`,
`docs/evidence/easy-preset-coverage.json`; docs 02/06/11/16.

- [ ] Inventory stable source preset IDs with every matched model/ECU/software
  applicability row; reconcile total counts/dispositions, no silent subset.
- [ ] Recover exact definition matching and live coded-data transport/block layout;
  reject directory-first selection and data-group-as-DID inference.
- [ ] Show actual current/unknown/custom values (D-40 preserves untouched custom
  bytes), capability reason and proposed
  changes; never show demo values as live or UI indexes as encoded values.
- [ ] Trace all applicable presets through fields/masks/value maps and account for
  source-restricted, unsupported and unresolved rows with evidence.
- [ ] Verify manual offline selections/decoders and DEMO; record owner live reads.

Exit: B-CODE-R genuine values and full catalog accounting. Unresolved applicable
presets keep the release open; they cannot be relabelled out of scope.

## B6b — composed easy writes, readback and recovery

Depends: B4 + B6a + B-CODE-W/restore/application/cycle/power contracts.
D-27–D-31 settle failure, lockout and acknowledgement policy; no open product gate.
Files: `app/coding.py`, `app/coding_db.py`, `app/security.py` as evidenced,
`app/operation_store.py`, coding/backups UI; docs 08/11/16/26.

- [ ] Recover complete write/security/integrity/block-order contracts; represent
  signed/authorized restrictions without key probing or bypass.
- [ ] Compose all selected changes against one complete baseline; preserve
  unrelated bits/unknown blocks and detect overlapping/conflicting selections.
- [ ] Persist baseline/intent, confirm affected ECUs/count and execute bounded
  writes; validate final application/job results and meaningful readback under
  D-29. Retain required cycle instructions without a false premature mismatch.
- [ ] Easy coding stops on failure, restores operation changes to baseline and
  checks restoration using its response/cycle/verification contract (D-27/D-29).
  Do not rollback because of a premature old-value read. Require evidenced restore paths;
  inspect failed restore and unreachable targets. Advanced-mode continuation is later scope.
- [ ] Remove write Cancel UI; warn/confirm definitive commitment and vehicle/host
  power responsibility (D-28). Investigate power facts before enforcing thresholds.
- [ ] Persist partial/mismatch/uncertain outcomes; reidentify/reread before
  user-selected recovery after any required cycle. Restore is a mutation with
  contract-specific completion checks, not guaranteed immediate observed verification.
- [ ] Account for every applicable preset in read/write/readback coverage; verify
  offline composition/interruptions and agree concrete owner mutation validation.

Exit: B-CODE-W and coding B-REC implemented/reviewed with exact applicability;
advanced editing remains later scope.

## B7 — review and release acceptance

Depends: required B feature implementations and their evidence.

- [ ] Review each slice with Python/Qt/protocol/write-integrity skills as applicable;
  record findings and resolutions, then rerun affected verification.
- [ ] Complete support matrix by transport/gateway/ECU/software/feature, keeping
  source support, offline checks and physical results separate.
- [ ] Visually check all required pages, limited/partial states, recovery and DEMO
  isolation; retain meaningful owner-operated F48/NBT observations.
- [ ] Verify Python 3.13 source launch on the owner’s Mac, offline asset closure
  and actual car flows (D-47–D-49). Record exact environment/outcomes. Windows,
  Intel Mac, packages, signing and public distribution materials are later work.
- [ ] Run full Ruff lint, Ruff formatting and mypy before each push; no suite.
- [ ] Open separate implementation PRs with evidence/contract links and precise
  acceptance limits; never mark pending vehicle/platform results completed.

Task B is complete only when spec 26's required release criteria are met or an
explicit owner scope change is recorded. Safe placeholders/static green gates
alone cannot close it.

## Interview-derived source investigations — 2026-10-29

- [ ] For each write and restore trace final job/application status, immediate
  stored-state visibility, activation/restart behavior and meaningful readback
  point; retain exact source evidence. Do not generalize one preset's cycle rule.
- [ ] Represent response-confirmed completion, cycle-required instructions and
  observed verification distinctly in UI and persisted operation records.
- [ ] Verify write lockout covers navigation, disconnect, competing requests and
  normal close while allowing a responsive progress display.
- [ ] Recover vehicle power limits/checks and investigate host power reporting;
  apply D-31 known-low block / unavailable-reading acknowledgement.

## English, locale and file coverage — 2026-10-29

- [ ] Audit all user-facing strings and source-derived coding/history/diagnostic
  text for English coverage (D-43), including missing English database entries;
  translate/review missing text without changing encoded identifiers or values.
- [ ] Detect system regional formatting/distance defaults where practical (D-44),
  retain English UI and Brazilian-format/km fallback. Verify date identity and
  unit round trips at the native-data boundary, including history additions.
- [ ] Implement simple ordinary unencrypted backup storage (D-45), portable
  schema/integrity checks and full diagnostic identifier logging/export (D-46).
  No password/encryption or VIN-masking feature is needed.

## Implementation slice — 2026-10-29

REA-backed connection/inventory/diagnostics, exact-identity coding snapshots and
portable backup storage are implemented in `codex/task-b-feature-recovery`.
Task B is **not complete**: local history/append/replacement flows, full preset writes and
restoration, actual MIL and DoIP inventory/address recovery remain open.
The supplied history utility's native read action is a Pro-only message.

See [recovered contracts](../docs/evidence/task-b-recovered-contracts.md) and
[verification/review](task-b-implementation-verification.md).

## B5 codec follow-up — 2026-10-29

- [x] Recover fixed ADD payload/field encoding and business-result position from
  four primary headunit PRGs; implement standalone NBT encoder/result codec.
- [x] Preserve all eight supplied local-file records byte-for-byte; retain
  unknown status/item/dealer/padding values and reject malformed/truncated input.
- [x] Independently review future/same-day checks, dealer/item/numeric limits,
  positive echo/business-result handling and absence of vehicle calls.
- [ ] Implement the revised local JSON/cards and mode-specific history execution/
  capacity/identity/session/activation/journal contracts in B5a/B5b. The old car-
  reader/baseline gate is retired by D-50–D-55; existing codec work is not full B5.

See [deep evidence](../docs/evidence/task-b-history-deep-investigation.md).

## B4 extension — history journal without a vehicle baseline

- [ ] Implement separate version 1 history-operation JSON journal persistence in
  app/history_files.py with immutable local_before/intent/requests/identity and
  vehicle_history_before=null. Use/extract durable publication, not dummy ECU
  baseline blocks. Keep operation-store v1 coding validators/files unchanged.
- [ ] Store canonical immutable/full-record hashes and ordered per-step state/
  requests/responses/unattempted work; never label history readback-verified.
- [ ] Update Backups UI schema routing, preview/export/delete and labels to show
  local history snapshots/journals separately from actual coding ECU backups.
  No history restore action promising the unreadable previous vehicle list.
- [ ] Check disk failure, integrity/version/type errors, partial outcomes, VIN and
  DEMO isolation, portability, explicit deletion and no car requests on imports.

This replaces B4's former complete-car-baseline prerequisite for history only.
