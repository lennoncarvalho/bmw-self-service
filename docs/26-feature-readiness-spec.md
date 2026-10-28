# Task B specification — functional BMW diagnostics, history and easy coding

Status: ready to start source investigation; wire contracts must be recovered
before implementing affected operations. Product choices explicitly marked
pending below must not become assumptions. Task:
[REA recovery](../tasks/rea-protocol-recovery.md). Sources/tools:
[doc 27](27-rea-source-guide.md). Runtime foundation:
[Task A spec](25-library-migration-spec.md).

## Release outcome

The owner needs ENET connection, real vehicle information and ECU discovery,
DTC reads/clearing, headunit-local service-history read/add, and live easy
coding reads/writes for the full applicable source catalog. History edit/delete/
replace and advanced coding remain eventual requirements but must
not delay this minimum slice. CBS read/reset remains future scope. Broad
source-supported F/G/U/I coverage is required as a design/research goal;
physical acceptance currently uses the owner's F48/NBT, not every BMW.

Research can start independently of Task A. App integration uses Task A's
merged API and must not create a second transport implementation. Missing
evidence leads to more source investigation or a precisely recorded blocker;
permanent “unavailable” placeholders do not satisfy this release outcome.

## Operation specification required before enabling a feature

Each operation gets a versioned contract with ID, purpose, source artifact/hash,
exact class/method/job and data dependencies, applicability, ECU/software and
definition identity, session/security prerequisites, full request sequence,
response/error codecs, lengths/units/scaling, timing and readback semantics.
Attach real REA Evidence references and a portable export. Templates and ledger
rules are in doc 27. Update docs 07/11/12/14/20 with recovered contracts or
link their exact versioned replacements; never paste hypothetical byte examples
into production code. Standard library behavior is a Task A concern.

## Feature acceptance

| ID | Required behavior | Completion evidence |
|----|-------------------|---------------------|
| B-CON | Discover actual transport/entity on selected wired interface, verify VIN/session, enumerate real ECU addresses and software identities | Source-derived connection/inventory branches plus complete retained owner-session traffic; no ASCII-name-only or F000 assumption |
| B-INFO | Read available mileage, voltage, I-level, FA/model/production metadata using matching job/codec; no fake successful empty value | Source-to-UI trace per field, meaningful decoded values or explicit supported-unavailable reason; explain first session's rejected reads |
| B-DTC-R | Scan discovered supported ECUs; preserve address/variant, status, descriptions and per-ECU coverage | Correct standard/vendor records, explicit skipped/failed/unsupported counts; no whole-car “no faults” from gateway-only empty data |
| B-DTC-W | One Clear All button targets all supported discovered ECUs after confirmation; continue on reachable ECUs if another fails, then reread faults and supported MIL | Per-ECU cleared/failed/not-attempted and post-clear results; partial remains partial; no saved report, per-ECU button or per-code button |
| B-HIST-R | Read the genuine headunit history without mutating it; decode fields/pagination and preserve unknown data | PRG/app trace through every transmitted buffer; NBT first, other headunits separately evidenced |
| B-HIST-W | Add local history while preserving existing entries and blocking exact duplicates | Complete add encoder, original backup, durable intent, checked response and independent readback comparison; no add routine relabelled read; edit/delete/replace later |
| B-CODE-R | Show easy presets with actual current ECU values, exact CAFD/software match and unknown/custom states | Data loaders/definition selection/current coded-data read traced together; no directory-first selection or mocks shown as live |
| B-CODE-W | Support every applicable source easy preset; compose selected changes against one baseline, preserve unrelated bits and verify the result | Multi-field/mask/block encoding, backup/intent/readback and recovery evidence; catalog applicability/exclusions explicit; no UI index used as ECU value |
| B-REC | Import/display eligible backups and recover interrupted history/coding operations | Match VIN/ECU/software, reread/compare first; only evidenced restore choices; local preview never labelled vehicle restoration |

For each row, publish source-evidenced, implemented, offline-inspected,
vehicle-validated, unsupported and unknown separately. Do not make an ECU
address or DID universal based on one vehicle. Security/session restrictions
must be represented; no source flag or ECU count proves write authorization.

All easy presets means every preset exposed by the supplied source dataset for
the matched model/ECU/software, not every preset on every car. Inventory stable
preset IDs and source applicability, then account for every row as implemented,
source-restricted, unsupported or unresolved with evidence. An unresolved
applicable preset is an open release item, not permission to silently shrink
the catalog. Decrypted definitions alone do not prove live data transport or
readback. No hand-selected sample may be presented as catalog completion.

## Shared state and UI contract

- Per field/ECU/feature distinguish loading, available, unavailable/unsupported,
  failed, cancelled and not attempted. Once VIN/session work, optional failure
  keeps the connection open (D-12). Gate only dependent operations.
- Expose capability and exact reason when a write lacks matched definitions,
  source-supported encoder, complete original data or readback support (D-14).
  Easy-mode UI must show current/proposed values, affected ECU and change count.
- Confirmation identifies the target and consequence. No write starts from
  browsing a page or loading a backup. Keep unrelated reads usable.
- Diagnostics presents faults grouped by ECU with available source-supported
  status categories, not only the current confirmed-only filter. One Clear All
  button acts across supported ECUs. Missing ECUs remain visible as coverage
  gaps; continue clearing reachable ECUs and report partial outcomes (D-19).
- Before adding history, reread the current list and compare date, mileage,
  dealer and service-item identity using documented canonicalization. Block an
  exact duplicate (D-20). Units/date interpretation must be evidence-backed;
  do not silently merge distinct service entries or auto-replay an uncertain add.
- Use CarWorker/QThread for every car operation. Cancel before send prevents
  it; cancel/disconnect after a mutation may have started produces uncertain
  outcome, followed by reread/compare. Do not promise atomic multi-ECU changes.
- Keep local headunit history, BMW backend history and CBS separate. No online
  synchronization, odometer programming, flashing or security bypass is implied.

## Backup, write/readback and recovery acceptance

Design a versioned operation bundle for coding/history with independent records:
baseline (immutable original raw/decoded data), intent, and observed readback.
Include operation/schema/app version, VIN, transport/ECU/hardware/software and
definition hashes, field/block identities, units, timestamps, integrity hashes
and phase/outcome. Write baseline/intent durably before first mutation; disk
failure blocks the write. Preserve unknown records/bits and the original backup.

Record states such as prepared, sending, awaiting-readback, verified, mismatch,
partial, uncertain and recovered with exact meanings in the implementation
plan. Acknowledgement alone is never verified success. Compare actual state to
intent using only source-evidenced normalization. Recovery after reconnect
reidentifies the car/ECU and rereads before choices; no append auto-replay.
Restoration is itself a mutation with eligible identity, backup and readback.
Fault clearing is explicitly exempt from saved backup/report requirements.

Exact persisted schema/UI labels are implementation design work, not reasons
to postpone research. Keep UI preferences in QSettings and operation records
in data files, with independent DEMO/live and per-vehicle storage.

## Product decisions and remaining detail

Confirmed in D-16–D-20: all-ECU faults, one Clear All, continue reachable ECUs
with partial outcomes, all applicable easy presets, history read/add first,
block exact duplicate entries. No per-ECU/single-code clear UI. Source evidence
determines the fault statuses/categories actually supported by each ECU.

Before affected UI/write implementation, settle precise MIL presentation,
history chronology and item/dealer field validation, multi-ECU coding partial-
write presentation and product choices around evidenced voltage limits.
If source behavior determines a validation rule, record that evidence instead
of asking the owner to invent protocol details.

These questions do not block evidence collection, inventory recovery, library
migration or genuinely supported reads. Record responses in doc 21 before
deriving the affected UI/write behavior. Never treat silence as agreement.

## Implementation file map

| Slice | Existing owners to review/change after the operation contract is recovered |
|-------|--------------------------------------------------------------------------|
| Connection/info | `app/connection.py`, `app/worker.py`, `ui/main_window.py`, `ui/vehicle_page.py`; consume Task A's adapter API |
| DTC display/Clear All | `ui/diagnostics_page.py`, `app/dtc_db.py`, extraction/data provenance and Task A's UDS service API; remove per-code clear UI and assumed group mappings |
| History read/add | `ui/service_history_page.py`, operation encoding/data files and `ui/backups_page.py`; replace disabled reader/old write assumptions from recovered contract |
| Full easy catalog | `app/coding_db.py`, `ui/coding_page.py`, `app/security.py`, dataset provenance; exact definitions, current bytes, composition and authorization |
| Shared backup/readback/recovery | History/coding workers, backup page and versioned data storage; introduce a shared module only after its schema/state design is recorded |
| Release integration | `main.py`, `requirements.txt`, asset resolution/packaging and docs 15/16/21; preserve source-independent offline app runtime |

Before each slice, list exact new/changed paths in Task B. Extracting network
operations from page classes into narrowly scoped services is allowed when
planned/reviewed; do not redesign Qt or introduce another transport stack.
Research source names may appear in internal docs/evidence, not shipped UI or
application data. Required third-party legal notices remain part of packaging.

## Delivery and verification

Research sequence: inventory/identity → vehicle info + DTC read/Clear All → history
read/add/readback → full easy-catalog read/encoder/readback → shared recovery
and broader variants. Build baseline/readback storage before enabling either
history or coding mutations; it is a shared dependency, not a final retrofit.
Use independent PRs for implementation slices, each with corrected specs and
evidence. [Task B](../tasks/rea-protocol-recovery.md) tracks the work packages.

Acceptance includes manual offline byte/codec inspection, DEMO/UI checks,
owner-operated car reads and separately agreed mutation validation. Do not
create an automated suite. Run all full-app static gates before push. Record
actual local runtime, Python 3.13/platform packaging checks and absent hardware
coverage. A fully green gate or one successful car does not certify every row.

## Task A integration handoff

The implemented owner/service API and identity-keyed codec registration pattern
are recorded in [Task A verification](../tasks/protocol-library-migration-verification.md).
Use that API once the integration PR merges; no feature creates another socket
consumer. Task A local library checks do not complete any B feature acceptance.
