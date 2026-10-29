# Task B — implementation plan

Status: product decisions consolidated, 2026-10-29; no feature contract newly recovered or code implemented.
Planning branch: `codex/task-b-recovery-plan`, from fetched `origin/main`
`db3c99f`. Task A is present in this baseline; its physical/platform/release
acceptance remains separate. Authority: [spec 26](../docs/26-feature-readiness-spec.md),
[research roadmap](rea-protocol-recovery.md), [source guide 27](../docs/27-rea-source-guide.md),
[decisions 21](../docs/21-product-decisions.md). Execution:
[ordered tasks](rea-protocol-recovery-tasks.md) and
[REA investigation checklist](rea-protocol-recovery-investigations.md).

## Scope and completion

Deliver B-CON/B-INFO, all-ECU B-DTC-R and one B-DTC-W Clear All, genuine
headunit-local history read/add, the entire applicable easy coding catalog and
B-REC recovery. History edit/delete/replace, advanced coding and CBS stay later
scope. Current acceptance is functional personal use from Python 3.13 source on
the owner’s Mac/F48/NBT (D-47–D-49). Windows/platform packages, signing and public
distribution are deferred. No cloud synchronization, flashing or authorization bypass.

Every enabled operation needs a retained source-to-send-to-decoder contract,
exact applicability and an implementation/verification link in the
[contract ledger](../docs/evidence/feature-contract-ledger.md). Track source-evidenced,
implemented, offline-inspected, physically validated, unsupported and unknown
independently. A disabled placeholder is a safe interim state, not completion.
A missing applicable preset remains an open release item.

## Baseline and design constraints

Observed locally in the merged source: Task A exposes `DiagnosticConnection`
`context`, `register_ecu`, `run_operation`, `submit_operation` and typed `request`
outcomes. `UdsServices.register_codecs` binds definitions to ECU identity and
hashes. These are the integration boundary; no second socket reader, protocol
owner, reconnect/replay loop or transport selection by chassis letter.

The historical retained session proves HSFZ/VIN on one F48/NBT. It does not
prove ECU inventory, optional-field mappings, full DTC coverage or writes.
Current optional reads still need replacement contracts. History/coding live
readers are disabled. The nested ClearWorker in `ui/diagnostics_page.py` has
legacy default addressing and response-only success accounting; it needs
explicit target validation and post-clear verification. Existing coding/history
writers, parser helpers and UI backup manifests are candidates to replace,
not verified encoders or restorable data.

Use Qt Widgets and CarWorker subclasses; keep pages as presentation/controller
code while extracting cohesive feature operations. Use structured result data
for available, unsupported, failed, cancelled and not-attempted outcomes, retain
raw bytes where needed and map errors to friendly UI text. Discard stale results
by connection generation. Never silently coerce a missing address to a gateway
or zero; transport addresses retain full width.

Default operation budget is 30 seconds from submission, including queueing,
session changes, pending responses and readback. Contract-specific exceptions
need evidence and documentation. A multi-ECU operation needs a published overall
budget and bounded per-ECU work, internal interruption handling and progress.
No user-facing write Cancel; D-30 blocks disruptive controls and normal closing. On ambiguous stream
failure, respect Task A connection closure; continue reachable targets only
through a valid connection, with reidentification if reconnection is required.
Never reuse a desynchronized stream merely to satisfy continue-on-failure.

## Delivery order and proposed files

Paths below are planned, not files already implemented. Reconfirm each slice's
exact paths against recovered contracts before coding. Amend this plan for any
new runtime module or dependency. Runtime data uses generic source-independent
names; proprietary source bundles/keys stay out of Git and shipped assets.

| Package | Deliverable and files | Prerequisites |
|---------|-----------------------|---------------|
| B1 | Reconcile `docs/evidence/local-artifact-inventory.json`; expand `docs/evidence/feature-contract-ledger.md`; create sanitized versioned contracts under `docs/`; correct docs 07/11/12/14/20 as findings arrive | Retained B0 Android smoke; source guide 27 |
| B2a | New `app/vehicle.py`: inventory, identity, capability/result records and evidenced operations; update `app/worker.py`, `ui/main_window.py`, `ui/vehicle_page.py`, `app/mock_connection.py` | B1 + B-CON/B-INFO contracts |
| B2b | Variant-bound codecs in `app/vehicle.py` and `app/uds.py` registration; exact software/definition identity and optional-field states | B2a inventory + per-field contracts |
| B3a | New `app/diagnostics.py`: ECU scan and coverage records; update `ui/diagnostics_page.py`, `app/dtc_db.py`; extraction corrections only with provenance | B2 inventory + B-DTC-R |
| B3b | Clear All operation in `app/diagnostics.py`; update diagnostics UI and docs 14/16/20 | B3a + B-DTC-W/MIL contracts and applicable owner decisions |
| B4 | New `app/operation_store.py`: durable bundles/state/recovery eligibility; update `ui/backups_page.py`, docs 13/16/26 | Identity schema + persistence/recovery design; precedes B5b/B6b |
| B5a | New `app/service_history.py`: genuine read/record codecs; update `ui/service_history_page.py`, docs 12/16 | B2 + B-HIST-R; NBT first |
| B5b | Add encoder/date-rule/completion flow in `app/service_history.py`; integrate operation store/history UI/backups UI | B4 + B5a + B-HIST-W/cycle semantics; D-32–D-39 |
| B6a | New `app/coding.py`: live reads/exact matching; update `app/coding_db.py`, `ui/coding_page.py`; catalog accounting in `docs/evidence/easy-preset-coverage.json` | B2 + B-CODE-R and complete source catalog inventory |
| B6b | Composed write/readback/recovery in `app/coding.py`; update coding/store/backups UI, review `app/security.py` without guessing keys | B4 + B6a + B-CODE-W/restore/cycle/power evidence; D-27–D-31 |
| B7 | Source/vehicle coverage, real owner Mac source acceptance and DEMO/UI; update README, docs 15/16/21/26 | All required slices; owner F48/NBT source flows, full applicable catalog accounting |

Research into B2/B3 and B5/B6 may advance independently; this is a dependency
schedule, not authorization to enable partially recovered mutations. Implement
read slices first. B4 design can advance before all encoders exist, but concrete
raw-state round trips and durable-write checks must precede either mutation.
D-29 makes completion contract-specific: meaningful readback when supported,
otherwise checked application response and required cycle instructions. Never
interpret a pre-cycle old value as failure. Easy mode needs an evidenced restore
path on established failure; advanced continuation remains later scope.
B3 clearing is exempt from saved backup/report requirements and does not depend
on B4. Implementation slices use fresh branches from then-current main and
separate PRs; this branch contains planning documents only.

## Evidence gates

For each feature, trace UI entry → variant/asset/job selection → complete request
sequence → transport → dispatcher → decoder → result. Retain original/member
hashes, exact methods/overloads or PRG instruction locations, tool versions,
actual Evidence IDs and portable export path/hash. Label static derivations,
simulations and vehicle observations separately. Include negative responses,
echo/length checks, units/scaling/sentinels, sessions/security, timing and
cancellation. A class name, label or decrypted asset alone closes no contract.

Reconcile existing extracts with original APK members before reuse. Inspect
SHM type/dependencies before selecting native/managed analysis; PRG requires a
format-aware parser/interpreter trace. Do not redo working REA setup or treat
Ghidra availability as native feature evidence. Request an additional source
only after recording the concrete unresolved chain and bounded searches.

## Durable operation design to finalize in B4

One versioned bundle links immutable baseline, intent and append-only observed
readbacks/events by operation ID. Carry schema/app version, VIN, transport,
ECU hardware/software, definition hashes, raw/decoded fields, units/timestamps,
integrity and outcome. Keep DEMO/live and vehicles isolated; preferences remain
in QSettings. Define atomic file publication, flush/fsync and platform semantics
before claiming durability. Backup/intent persistence failure blocks sending.

| Phase/outcome | Meaning |
|---------------|---------|
| prepared | Original state and intent durably saved; no mutation sent |
| sending | Transmission may have started; interruption cannot imply no effect |
| response-confirmed | Validated application/job completion; no observed-value claim |
| cycle-required | Operation requires documented ignition/reconnect instructions; link response/observations |
| awaiting-readback | Meaningful supported verification is pending |
| verified | Independent readback matches source-evidenced intended semantics |
| mismatch | Meaningful post-prerequisite readback differs from intended state |
| partial | Known mixed per-target results; retain each target's outcome |
| uncertain | Required application outcome cannot be established; block replay |
| recovered | User-selected recovery completed under its response/cycle/verification contract |

Aggregate partial and uncertain states must retain individual target phases;
no single success flag replaces them. Recovery reidentifies and rereads before
offering choices, applying required cycle semantics first. Restore is itself
a backed-up mutation with evidenced response/cycle/completion checks.
History append never auto-replays; original/unknown records and unrelated coding
bits survive. Legacy UI-only backup manifests may be displayed as previews but
cannot be promoted to eligible vehicle restoration.

## Resolved product rules and remaining investigations

[Doc 21](../docs/21-product-decisions.md) D-21–D-49 settles the interview:
refuse multiple vehicles, limited VIN troubleshooting, batch page publication,
conditional assisted setup; distinct MIL/coverage; no write Cancel, app lockout,
power acknowledgement and easy rollback on established failure; cycle-aware
completion; preserving history rewrite, no future/same-day additions, free dealer,
multiple items and entered mileage without odometer validation; untouched Custom
coding; retained/deletable portable plain backups; English text, system regional
formats with Brazilian/km fallback and full unmasked logs; Mac source-first use.

No product interview gate remains for this milestone. Recover network need,
source encoders, exact field constraints, stored-value/cycle/response semantics,
restore support and power checks through the REA checklist. If a new genuine
behavior tradeoff appears, state the evidence and bounded choice rather than
reopening settled requirements. Numeric limits are not preference questions.

## Presentation and local data design

Plan `app/formatting.py` for shared locale/distance/date presentation and input
normalization, with consumers in vehicle/history/coding/diagnostics pages.
Native units/calendar identity remain intact. Final path/module scope is reviewed
before implementation. Audit English coverage in `app/coding_db.py`,
`app/dtc_db.py`, source catalogs, `coding_data/`, `dtc_descriptions.db` and UI;
use extraction/translation scripts only with retained provenance. Portuguese later.

B4 uses straightforward ordinary unencrypted versioned files, with retained raw
state and durable baseline/intent. All backups persist until explicit deletion;
allow portable import/export, validate schema/integrity and gate restoration by
identity/software/definitions. Import never writes. No password UX or automatic
pruning. Preserve full diagnostic identifiers in logs/exports; do not commit
private captures merely to retain evidence. No automatic VIN masking.

## Verification and completion gates

Each slice retains manual offline byte/codec checks for recovered sequences,
errors, malformed/truncated responses, deadlines and cancellation; DEMO/UI
checks are distinct. No automated suite or `tests/`. Review Python correctness,
Qt lifecycle and vehicle-write integrity with applicable project skills, applying current
D-29 over older unconditional readback guidance.

Before every push run full `scripts/preflight.sh`: Ruff lint, Ruff format check
and mypy over all app/UI/main targets. Run Python 3.13 source launch on the owner’s Mac. Packaged release/signing,
Intel Mac and Windows checks remain later milestones (D-48/D-49). Record actual results, never inferred coverage.

Owner-operated acceptance starts with read-only identity/inventory/info/DTCs.
History/coding/Clear All physical mutation validation requires a separately
agreed concrete procedure after encoder, prerequisites and contract-specific completion are reviewed.
Retain source/operation summaries and full unmasked local diagnostic captures. One F48/NBT does not establish
fleet coverage. B7 remains open for missing required acceptance, even when all
code and static checks pass.

## Implementation execution — 2026-10-29

Owner authorizes unattended REA-led implementation, independent review, fixes,
verification and PR. Branch `codex/task-b-feature-recovery` starts at current
`origin/main` and carries the approved planning commits. Recover source-wide
F/G/U/I selection and contracts, rather than a chassis-specific shortcut.

First recovered correction: diagnostic inventory uses gateway `22 3F07`,
BE16 payload byte count and one-byte ECU addresses, followed by `22 F150`
three-byte variant identification. Remove the unsupported F000/text parsing
and optional DID guesses. Recover normal, information and permanent memories
separately. SHM is native x86/Delphi; NBT PRG add/erase jobs require tracing,
not CIL inspection or treating the local `.bmwsh` format as a vehicle read.

## History/runtime follow-up plan and disposition — 2026-10-29

1. Trace all native form handlers/resources and common network callers beyond
   the Lite read stub; retain coordinates and hashes. Done; no dormant complete
   reader confirmed, with indirect-call/coverage limits explicit.
2. Independently decode the four headunit ADD jobs and local sample. Done;
   fixed19-byte header, seven-byte dealer and eight-byte items. Variable-NUL
   hypothesis rejected against native display offsets and actual file.
3. Implement standalone immutable local codec, preserving unknown originals,
   new-entry validation, NBT payload and checked business-result decoder in
   app/service_history.py. Do not enable vehicle send without original state.
4. Audit app imports/dependencies/startup/packaging for REA separation; remove
   misleading source-tool/security-algorithm comments from app/security.py and
   app/coding_db.py; document development-only rule in AGENTS.md.
5. Independent review, offline golden/boundary/sample checks, full preflight,
   then update the existing unmerged draft PR. No vehicle mutation validation.
