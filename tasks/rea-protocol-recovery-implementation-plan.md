# Task B — implementation plan

Status: planned, 2026-10-28; no feature contract newly recovered or code implemented.
Planning branch: `codex/task-b-recovery-plan`, from fetched `origin/main`
`db3c99f`. Task A is present in this baseline; its physical/platform/release
acceptance remains separate. Authority: [spec 26](../docs/26-feature-readiness-spec.md),
[research roadmap](rea-protocol-recovery.md), [source guide 27](../docs/27-rea-source-guide.md),
[decisions 21](../docs/21-product-decisions.md). Execution:
[ordered tasks](rea-protocol-recovery-tasks.md).

## Scope and completion

Deliver B-CON/B-INFO, all-ECU B-DTC-R and one B-DTC-W Clear All, genuine
headunit-local history read/add, the entire applicable easy coding catalog and
B-REC recovery. History edit/delete/replace, advanced coding and CBS stay later
scope. No cloud history synchronization, flashing or authorization bypass.

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
budget and bounded per-ECU work, cancellation and progress. On ambiguous stream
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
| B5b | Add encoder/duplicate/readback flow in `app/service_history.py`; integrate operation store/history UI/backups UI | B4 + B5a + B-HIST-W + history decisions |
| B6a | New `app/coding.py`: live reads/exact matching; update `app/coding_db.py`, `ui/coding_page.py`; catalog accounting in `docs/evidence/easy-preset-coverage.json` | B2 + B-CODE-R and complete source catalog inventory |
| B6b | Composed write/readback/recovery in `app/coding.py`; update coding/store/backups UI, review `app/security.py` without guessing keys | B4 + B6a + B-CODE-W + partial-write/voltage decisions |
| B7 | Source/vehicle coverage, DEMO/UI and package acceptance; update README, docs 15/16/21/26, packaging only as needed | All required slices; outstanding platform/vehicle access recorded |

Research into B2/B3 and B5/B6 may advance independently; this is a dependency
schedule, not authorization to enable partially recovered mutations. Implement
read slices first. B4 design can advance before all encoders exist, but concrete
raw-state round trips and durable-write checks must precede either mutation.
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
| awaiting-readback | Application response received; state unverified |
| verified | Independent readback matches source-evidenced intended semantics |
| mismatch | Complete readback differs from intended state |
| partial | Known mixed per-target results; retain each target's outcome |
| uncertain | Send/effect/readback cannot be established; block replay |
| recovered | Reidentified, reread and verified a user-selected evidenced recovery |

Aggregate partial and uncertain states must retain individual target phases;
no single success flag replaces them. Recovery reidentifies and rereads before
offering choices. Restore is itself a backed-up/readback-verified mutation.
History append never auto-replays; original/unknown records and unrelated coding
bits survive. Legacy UI-only backup manifests may be displayed as previews but
cannot be promoted to eligible vehicle restoration.

## Owner decision gates

Do not ask the owner to invent protocol constants. Source-derived constraints
come first; pending product choices remain pending until answered in doc 21.

| Before affected implementation | Required decision/work |
|--------------------------------|------------------------|
| Connection UX | Assess D-13 series picker benefit; multiple-car selection and identity/limited-state presentation |
| Clear All/MIL UI | MIL presentation when supported, unavailable or unchanged after clear |
| History add | Chronology, dealer/item/date/distance validation where not fixed by source; exact duplicate rule D-20 already approved |
| Coding writes/recovery | Multi-ECU partial/uncertain presentation and evidenced voltage preconditions |
| Backup/release UI | Retention/import/export/privacy choices when that slice needs them; exact app license/distribution materials remain release work |

These do not block source research or planning. Network elevation/DHCP is a
separate unresolved product flow, not an implicit connection fallback.

## Verification and completion gates

Each slice retains manual offline byte/codec checks for recovered sequences,
errors, malformed/truncated responses, deadlines and cancellation; DEMO/UI
checks are distinct. No automated suite or `tests/`. Review Python correctness,
Qt lifecycle and vehicle-write integrity with applicable project skills.

Before every push run full `scripts/preflight.sh`: Ruff lint, Ruff format check
and mypy over all app/UI/main targets. Run Python 3.13 and relevant packaging
checks at release integration; package/data/legal closure covers macOS arm64,
Intel and Windows x64. Record actual results, never inferred coverage.

Owner-operated acceptance starts with read-only identity/inventory/info/DTCs.
History/coding/Clear All physical mutation validation requires a separately
agreed concrete procedure after encoder, prerequisites and readback are reviewed.
Retain sanitized results and local full captures. One F48/NBT does not establish
fleet coverage. B7 remains open for missing required acceptance, even when all
code and static checks pass.
