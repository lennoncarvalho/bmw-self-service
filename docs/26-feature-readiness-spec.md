# Task B specification — functional diagnostics, history and easy coding

Status: product decisions consolidated 2026-10-29; ready for evidence-driven
implementation. BMW wire contracts remain to be recovered before enabling their
operations. Authority: [owner decisions 21](21-product-decisions.md).
[Implementation plan](../tasks/rea-protocol-recovery-implementation-plan.md),
[development tasks](../tasks/rea-protocol-recovery-tasks.md),
[REA checklist](../tasks/rea-protocol-recovery-investigations.md),
[source guide 27](27-rea-source-guide.md).

## Current acceptance target

A working Python-source application on the owner's Mac and F48/NBT: ENET
connection, real vehicle information, complete discovered-ECU fault display and
one Clear All, headunit-local history read/add, every applicable matched easy
preset and usable backup/recovery. Real owner-operated results are required;
DEMO, placeholders, source claims and static green gates alone are insufficient.

Windows is available but deferred. Packaging, signing/notarization, Intel Mac
validation and public distribution are later milestones (D-47–D-49). Preserve
cross-platform design and existing legal notices without making release packaging
an obstacle to working source flows. Broad source-supported F/G/U/I applicability
remains the research/design goal, not universal physical validation. Advanced
coding, user-facing history edit/delete/replace and CBS remain later scope.

Task A PR #12 is merged. Use its single owner/API and selected libraries;
Task B must not introduce another transport stack or socket consumer. Retain
Qt Widgets/CarWorker architecture, offline runtime and no automated suite.

## Required source contract before an operation is enabled

Retain versioned operation ID, artifact/version/full hash, exact class/method/job
or instruction, dependency/member identities, actual REA Evidence IDs and
portable export path/hash. Trace selection → complete request sequence → send →
dispatch → decoder → displayed result. State endpoint, variant/software/definition,
session/security prerequisites, field layout/units/scales/sentinels, echoes/errors,
P2/P2*/overall deadlines, keepalive, interruption and completion/cycle semantics.
Label static derivation, simulation and actual vehicle observations separately.
Correct docs 07/11/12/14/20 or link exact replacement contracts. Strings, labels,
asset decryption and smoke inspection do not close a wire contract.

## Feature acceptance

| ID | Required behavior | Completion evidence |
|----|-------------------|---------------------|
| B-CON | Selected wired interface/chassis hint; actual transport/session/VIN; real ECU addresses/software | Source-derived inventory and owner retained session; no chassis-to-transport or fixed-F000/ASCII assumption |
| B-INFO | Evidenced mileage, voltage, I-level, FA/model/production fields | Source-to-UI trace and meaningful owner values or explicit supported-unavailable reasons; explain original failed reads |
| B-DTC-R | All discovered supported ECUs, source-supported fault categories/details/descriptions, per-ECU coverage | Correct records and success/failed/unsupported/not-attempted accounting; partial empty scan never means no whole-car faults |
| B-DTC-W | One confirmed Clear All over identified supported targets, continue reachable targets, reread supported faults/MIL | Named scan gaps; per-target application and post-clear results; no saved backup/report or per-code/per-ECU clear buttons |
| B-HIST-R | Genuine nonmutating complete headunit history read | NBT first; complete records/unknown fields and pagination from source-to-buffer-to-decoder trace |
| B-HIST-W | Add one multi-item dated entry without losing existing history | Native append or preserving full-list rewrite; complete backup/intent, date rules, evidenced application completion/cycle instructions |
| B-CODE-R | Every applicable matched easy preset with actual current values | Exact ECU/software/CAFD and live bytes; complete catalog accounting; untouched Custom values preserved |
| B-CODE-W | Compose selected presets against one complete baseline; preserve unrelated data | Exact masks/blocks/authorization/encoding, backup/intent, application completion and meaningful verification; easy failure rollback path |
| B-REC | Portable backup preview/import and eligible restoration/interruption recovery | Identity/integrity compatibility, reidentification and meaningful reread/compare before user-selected recovery; import itself never writes |

Track source-evidenced, implemented, offline-inspected, vehicle-validated,
unsupported and unknown separately for each variant. All applicable presets
means the full supplied catalog for matched model/ECU/software, with stable IDs
and explicit dispositions. An unresolved applicable preset remains open, not a
silently excluded subset. Fleet hardware validation is not implied by one car.

## Connection, initial loading and diagnostics

D-21: refuse connection if multiple vehicles respond on the chosen interface;
require only one, with no vehicle chooser or first-response selection. D-22:
responsive gateway without verified VIN permits limited troubleshooting/logs;
vehicle-dependent operations remain disabled.

D-23: prefer independent page loading; publish a page's initial results together
after its batch settles, with explicit failure/unavailable/coverage states. No
piecemeal field population. Global loading is an acceptable fallback. Verified
identity remains connected after optional failures (D-12); gate dependent features.
Assess D-13 chassis-picker simplification using sources; selection is only a hint.

D-24: normal experience should need chassis and adapter selection without manual
configuration. Recover reference behavior first; assisted setup is authorized
conditionally if beneficial and straightforward. Record platform need, owned
changes/elevation/cleanup; assume neither DHCP necessity nor privileged fallback.

D-25: emissions MIL On / Off / Unavailable is separate from fault count and uses
an actual supported read. After Clear All show the observed state, including On.
D-26: incomplete scan coverage permits clearing identified supported targets,
with gaps named in confirmation. Continue after ECU-local failure on a usable
stream; respect Task A closure after ambiguous transport failure and explicitly
account for remaining targets. Never reuse an invalid stream to force continuation.

## Definitive writes, completion and recovery

Before coding/history mutation identify VIN/ECU/software/definitions, read complete
original data and durably save baseline/intent. Missing original data, unmatched
encoder or disk failure blocks sending. Confirmation shows target, changes,
consequences, power requirement and the user's commitment/responsibility.

D-28/D-30: no write Cancel. Block disruptive navigation, disconnect, competing
operations and normal closing throughout write/check/rollback. Keep the GUI
responsive with progress. External power/cable/process loss still creates actual
partial/uncertain records and recovery instructions; no false success or replay.

D-31: block known insufficient power; if reliable readings are unavailable,
require acknowledgement of adequate vehicle/device power. Source/platform
investigation supplies checks and applicable limits, not invented thresholds.

D-29 supersedes universal immediate readback. Recover each operation's final
application/job result, stored-value visibility and activation/restart semantics.
When meaningful, independently read and compare. Where a full ignition cycle,
new connection or unsupported readback prevents immediate verification,
response-confirmed completion with specific instructions is sufficient. Record
response-confirmed and observed-verified outcomes distinctly. Transport ACKs
alone are insufficient. Do not wait indefinitely for a user cycle or roll back
merely because an old value was read before the required cycle.

D-27: easy coding stops and restores operation changes after established failure,
using an evidenced baseline restore encoder and contract-specific completion
checks. Failed/unreachable restoration remains explicit; no atomicity guarantee.
After interruption, reidentify/reread when meaningful (cycle first if required),
then user-selected recovery (D-08); no blind restoration/replay. Advanced mode,
when later implemented, continues after definite ECU-local rejection on a healthy
connection. Both modes share the same underlying verified engine.

## History add rules

D-32 permits the simplest evidenced native append or full-list read/merge/rewrite.
Preserve every existing record and unknown field; block if preservation cannot
be established. Backup alone is not permission to lose records. Internal rewrite
does not expose user-facing editing/deletion/replacement in this milestone.

D-33: picker and operation validation reject future dates. D-35: reject a new
entry on any existing calendar date, regardless of other fields. Preserve any
same-day entries already present; never silently shift or merge dates. Recheck
against fresh complete history before sending.

D-34: dealer/garage is free input within actual field/encoding limits. D-38:
multiple supported service items in one dated entry. D-39 supersedes D-36:
write user-entered mileage without a current-odometer read/check. Allow mileage
conflicting with surrounding history (D-37). Validate actual numeric/unit/range
encoding only; user accepts entered-mileage responsibility. Optional B-INFO
mileage remains independent. Never replay an uncertain append/rewrite.

## Coding, local data and presentation

D-40: display existing non-preset values as Custom; preserve untouched original
bytes. Explicit supported preset selection may replace one. Never encode a UI
index, select the first definition directory, or infer write permission from flags.
Compose multi-field/mask/block changes against one baseline, detect conflicts
and preserve unrelated/unknown data. Modern authorization restrictions stay visible.

D-41/D-42/D-45: simple ordinary unencrypted versioned files; retain all backups
until explicit user deletion. Explain loss of recovery material without a permanent
unresolved-backup deletion ban; active write lockout still applies. Allow portable
export/import with schema/integrity validation; vehicle/ECU/software/definition
compatibility gates restoration, not local preview. Import alone never mutates.

Keep immutable baseline, intent, responses, observations and restoration events
separate by operation ID; include identity, units, versions/hashes and timestamps.
Persist prepared/sending/response-confirmed/cycle-required/verified/mismatch/
partial/uncertain/recovered states without mislabelling response-only evidence.
Storage location/schema/durable publication are implementation design, not pending
product interviews. QSettings is for preferences; isolate DEMO/live/per-vehicle data.

D-43: all UI and user-facing descriptions/catalog labels are English; Portuguese
later. Resolve translation gaps; do not hide a fault for missing description.
D-44: system regional date/number formatting and distance-unit defaults where
practical; Brazilian-format/km fallback, English UI throughout. Preserve native
values/units and calendar identity. D-46: full unmasked diagnostic logs/exports,
including VIN; private evidence need not be committed. Runtime remains offline.

## Delivery and verification

Implement B1–B7 from the ordered tasks, on fresh branches/separate PRs as planned.
Use manual offline byte/codec/error/timing checks and visual DEMO checks without
creating a suite. Run full `scripts/preflight.sh` before every push: Ruff lint,
Ruff format check and mypy over all app/UI/main targets. Verify Python 3.13 source
launch on the owner's Mac and actual vehicle outcomes with retained traffic.
Agree concrete physical write procedures once encoders/prerequisites/completion
contracts are reviewable. Packaged/platform/public-release checks are deferred.

No product decisions remain unanswered for starting this milestone. Remaining
protocol questions are enumerated in the REA checklist; unsupported interim
states do not satisfy a required feature. Report precise evidence gaps and
validation limits rather than claiming success from static gates or library reuse.

## Implementation slice — 2026-10-29

REA-backed connection/inventory/diagnostics, exact-identity coding snapshots and
portable backup storage are implemented in `codex/task-b-feature-recovery`.
Task B is **not complete**: history read/preserving add, full preset writes and
restoration, actual MIL and DoIP inventory/address recovery remain open.
The supplied history utility's native read action is a Pro-only message.

See [recovered contracts](evidence/task-b-recovered-contracts.md) and
[verification/review](../tasks/task-b-implementation-verification.md).

## History codec and runtime boundary follow-up — 2026-10-29

[Deep investigation](evidence/task-b-history-deep-investigation.md) records extended Lite native tracing and four primary
headunit ADD jobs. The key-only dormant-reader assertion remains unconfirmed.
Standalone `app/service_history.py` now preserves local records and encodes the
recovered NBT ADD body with checked final application status; no vehicle send
worker is enabled without a complete baseline/execution contract. Fixed7 dealer
padding is proven; the variable-NUL hypothesis was disproven by native offsets
and a byte-for-byte round-trip of all eight supplied records. Complete headunit
history read and Task B completion remain open. REA supports development recovery
of code/data/contracts and is never a runtime dependency.
