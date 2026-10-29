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
- [ ] Recover history and coding chains as later reads require; inventory every
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
- [ ] Implement immutable baseline, separate intent/readbacks and state events;
  preserve individual target states in aggregate partial/uncertain outcomes.
- [ ] Block writes on incomplete backup, corrupt data or persistence failure.
- [ ] Define eligible portable exports/imports and legacy-preview-only manifests;
  isolate DEMO/live and per-vehicle data. Retain all backups until explicit user
  deletion (D-41); no automatic pruning. Vehicle compatibility gates restoration,
  not local preview/import (D-42); validate imported schema/integrity; retain full unmasked diagnostic identifiers (D-46).
- [ ] Implement recovery reidentification/reread/compare and capability filtering;
  no automatic replay or inferred restore ability.
- [ ] Manually inspect disk-full/permission/interruption/corruption/mismatched
  identity cases and process-restart discovery of pending bundles.

Exit: durable pre-send storage and recovery eligibility verified offline;
feature restoration still depends on each actual encoder/completion/cycle contract.

## B5a — genuine local history read

Depends: B2 + B-HIST-R. Files: new `app/service_history.py`,
`ui/service_history_page.py`; docs 04/12/16.

- [ ] Identify SHM type/dependencies and follow read action through PRG execution
  to every buffer; distinguish local backup serialization from wire records.
- [ ] Recover NBT records, pagination, date/distance/dealer/items and unknown
  fields; account separately for CIC/EVO/MGU branches and restrictions.
- [ ] Replace disabled reader with evidenced read only; delete/retire contradictory
  legacy parser/routine assumptions as their replacements are proven.
- [ ] Verify offline parsing, empty vs invalid state and DEMO/UI; retain owner
  read-only history comparison before any append validation.

Exit: B-HIST-R actual state and raw unknown data preserved; loading never mutates.

## B5b — history add and safe recovery

Depends: B4 + B5a + B-HIST-W application/encoding/cycle contract. D-32–D-39
settle product rules; recover only actual format/field limits from sources.
Files: `app/service_history.py`, `app/operation_store.py`,
`ui/service_history_page.py`, `ui/backups_page.py`; docs 12/16/26.

- [ ] Recover native append or full-list replacement encoder (D-32),
  authorization/session and contract-specific completion/read semantics; verify
  complete existing/unknown-record preservation. SHM overwrite behavior is an
  owner observation to investigate, not retained wire evidence.
- [ ] Reread before add, compare evidenced calendar dates and block every
  same-day addition (D-35); reject future dates in picker and operation validation.
  Preserve all existing entries; support free dealer input within actual limits.
- [ ] Use entered mileage without a current-odometer query/check (D-39); permit
  historical mileage conflicts (D-37). Validate actual numeric/unit/range format.
  Support multiple items per entry (D-38); trace the owner-referenced `.bmwsh`
  example through actual headunit encoding.
- [ ] Persist original and intent before send; preserve all existing/unknown data;
  apply meaningful readback or checked application completion/cycle instructions
  under D-29; keep response-confirmed and observed verification distinct.
- [ ] Handle forced interruption, meaningful mismatch, restart and uncertain add
  without replay; no write Cancel UI;
  offer only source-supported recovery after reread.
- [ ] Keep edit/delete/replace out of this slice. Verify offline and agree the
  concrete owner append/readback procedure before car mutation.

Exit: B-HIST-W/B-REC history path includes backup, date rules, evidenced completion/cycle semantics and
reviewed recovery; physical outcome separately recorded.

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
