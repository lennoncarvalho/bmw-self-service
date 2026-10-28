# Source-first BMW protocol recovery plan

Status: ready for review; investigation plan, not completed reverse engineering.
Created 2026-10-28 after [the first retained car session](../docs/23-first-vehicle-session.md).
Scope: ENET support across source-supported BMW F/G/U/I gateway/ECU/software
families; retain the existing exclusion of E-series and other adapters.

## Outcome and constraints

Derive implementable protocol contracts from supplied applications and their
data, then use recorded traffic and vehicles to validate our implementation.
The owner's car is not the source from which we invent universal mappings.
“Any BMW” remains the coverage objective, measured against the reference apps'
actual supported branches and restrictions, not a promise based on model year.

No app implementation is changed by this plan. Each later implementation starts
on a fresh `codex/` branch and new PR. Preserve no-automated-suite policy: do not
create `tests/`, even though offline byte analysis is possible. Keep all car I/O
in CarWorker threads and source-tool names out of shipped code/assets.

## Established starting point

- Two HSFZ connections and VIN reads worked in the retained session; no evidence
  of ACK misassociation in its 28 diagnostic transactions.
- FA, mileage, voltage and topology requests were rejected. I-level was decoded
  as a tab; empty FA was reported as successful. DTCs scanned the gateway only.
- Doc 02's limitations list says only `ESeriesVehicleInterface` had been analyzed.
  Doc 03's sensor JSON is explicitly inferred. Doc 07's topology example is
  conceptual. Docs 19/20 already identify the app's fixed reads as unverified.
- The gap is an incomplete evidence-to-implementation chain. This does not
  prove earlier REA calls were wrong; distinguish missing retained evidence,
  incomplete research and later implementation drift per claim.

## Evidence and deliverables required for every operation

Every contract must retain:

1. Original artifact name/version/full SHA-256; extraction identity and tool
   versions; actual REA Evidence IDs and portable export, when produced.
2. Entry point → variant/ECU selection → dependency assets/job → encoder →
   transport send → response dispatcher → decoder → displayed result, with
   exact classes/methods/overloads, offsets or PRG job/instruction locations.
3. Endpoint/tester addressing, transport/activation, session/security requirements,
   complete request sequence, exact request/response examples and byte layout.
   Mark static examples separately from observed traffic.
4. Length, endianness, sign, scale, units, sentinels, echo checks, NRC handling,
   P2/P2*/overall deadlines, keepalive, cancellation and late-response behavior.
5. Applicability by gateway/ECU/software/data version; exact definition selection,
   prerequisites, explicit unsupported behavior and unresolved branches.
6. App implementation location and acceptance checklist. Binary strings,
   UI labels, function names and simulation data alone do not close the chain.

Store a finding ledger and corrected operation contracts in `docs/evidence/`
and `docs/`; keep large/private originals and raw logs locally with integrity
references. Never invent an Evidence ID or commit keys, personal config, VINs
or entire proprietary source bundles. Keep standalone runtime dependencies
separate from research tools and reference applications.

## Phase 0 — restore reproducible analysis capability

Fresh checks in this investigation:

- No REA MCP tools are advertised to this session.
- Cached public REA launcher 6.8.0 runs with bundled Node 24.22.1. `npx` is
  absent from the current shell PATH; this is a launcher issue, not missing Node.
- `doctor --client codex --json` reports missing Codex registration and missing
  configured JADX, Ghidra, Hopper, IDA and Kuna providers. It does not establish
  a working live server. No provider or host configuration was changed.
- The project REA skill is present; doctor's missing shared skill copy is not
  a reason to duplicate it. Do not repair other clients merely because they
  appear in informational diagnostics.

Execution order:

1. Check existing configuration/provider locations without exposing unrelated
   config. Prepare REA's scoped Codex `setup --dry-run --json`; show exact
   paths, backups and skill replacements before any configuration write, per
   `.agents/skills/reverse-engineer-anything/references/connection-and-recovery.md`.
2. Select only needed engines: Android requires a full Java 17+ JDK and supplied
   `jadx-headless-mcp` 0.7.1 JAR configured through `REA_JADX_MCP_JAR`.
   Native/managed routes depend on the actual SHM/PRG artifact type. Do not
   install every provider or assume a managed decompiler handles native code.
3. After authorized setup, reconnect the client, inspect actual tool schemas
   and `binary_session` availability. A green doctor alone is insufficient.
4. Smoke-inspect one actual APK using `inspect_android_package`, then inspect
   a known class/method; export complete Evidence. For SHM, inventory/identify
   before selecting `inspect_managed_artifact` or native `open_binary`.
5. Reuse existing smali/assets after validating their correspondence to the
   original APK. Until that link is proven, label them local extracted-source
   observations with unknown extraction provenance. Do not discard them or
   repeatedly re-decompile whole apps to answer focused questions.

Exit: a successful real analysis with retained artifact identity/evidence and
working relevant providers, or precise remaining blockers with a supported
fallback. Tool setup is work to perform, not claimed complete by this plan.

## Phase 1 — artifact and evidence reconciliation

Rehash originals, reconcile old abbreviated hashes/`ev_...` references with
recoverable exports, and record unsupported claims separately. Full hashes of
the following files were freshly checked and match the existing inventory:

| Artifact | SHA-256 |
|----------|---------|
| BimmerCode 4.25.04-12743 APK | `fc6eedeb741cbec49f46c126f8c72dac6a3dd1455f8a993c028695642459b728` |
| BimmerLink 2.36.1 APK | `da6f5b39efaa590fce68782f439c1b8f1b9f09ed41344055b8ff80666cae00d5` |
| SHM.exe | `2d6bb52808f1754ac9334958530c5b2c60ec373fa35b674f28bdb34dc93cf92a` |
| NBT.prg | `e94e3b4434c9f8563448ee0b89153ed62856cce3d72db61b18373b184f896415` |

Also inventory/hash relevant CIC/NBTEVO/HU_MGU PRGs, ECU groups, encrypted
assets, extracted datasets and interpreter dependencies as they enter scope.
Inspect existing `BimmerDaten/decoderPrg.py` and `ediabasx` parser/decompiler/VM
and transport source; independently verify relevant paths against originals.

Exit: each reused claim is retained/reproducible, contradicted, or unresolved;
all analysis targets and extraction relationships have explicit identities.

## Phase 2 — connection, identity and complete ECU inventory (first priority)

Trace reference apps' Connect entry points through adapter filtering, address
selection, discovery, multiple-vehicle handling, gateway selection, HSFZ/DoIP
decision, routing activation, tester addressing, VIN and ECU enumeration.
Trace F/G/U/I branches independently, including electric/i-series variants;
do not extrapolate ESeries logic or choose transport from a chassis letter.

Recover the actual inventory mechanism, its decoder and ECU address/software
identities. Do not assume a single F000 DID or ASCII/fixed-record SVT structure.
Trace how apps resolve a logical ECU, variant, diagnostic group/PRG and dataset;
preserve missing/unsupported inventory states. Establish session timing and
keepalive behavior, including whether this app's HSFZ heartbeat is appropriate.

Outputs: connection state machine and variant selection table, real inventory
contract, updated docs 07/10/20 (and DoIP portions of 01/05), implementation
mapping for `app/connection.py`, controller and vehicle page.

Exit: exact source-backed path from connection to an addressable ECU inventory;
the retained F48 session's rejection is explained without substituting a guess.
Unknown addresses must never silently become `0x00`.

## Phase 3 — vehicle information and complete diagnostics (next release slice)

Follow data loaders as well as code. Concrete local seeds to verify with REA:

- `bimmerlink_extracted/smali/j6/h.smali` loads `dat/ecu-variants.enc`;
  `j6/e.smali` loads `dat/%s.enc`.
- `smali/io/sgsoftware/bimmerlink/asyncTasks/FileDecompression.smali` contains
  decryption/decompression logic. Recover its exact format and dependencies.
- `BMWSensorValueDeserializer.b()` → `j6/m.<init>` exposes fields such as
  `id`, `resultName`, `unit`, `label`, `byte`; follow incoming callers into
  the execution engine. This is not doc 03's invented generic DID/formula JSON.

Trace mileage, voltage, I-level, FA/vehicle identity through job selection,
request construction and decoding. Determine whether model/year/production
date come from vehicle data, reference lookup or external services. Preserve
offline operation and leave unavailable data explicit.

For DTCs, trace ECU inclusion/exclusion, session prerequisites, fault-memory
variants, status masks and complete record codecs. Treat confirmed, current,
pending, history, details/snapshots and emissions MIL as separate contracts.
Trace exact ECU-specific description lookup and extraction collisions. Fault
clearing later needs its own source-backed target/group and post-clear reread;
the owner requires no saved report/backup for that operation.

Outputs: corrected docs 03/07/14/20, versioned operation/decoder contracts,
diagnostic coverage schema and app change plan. Record unsupported reads as
unavailable; never label an empty task value a successful decode.

Exit: source-derived endpoint/job/codec for every enabled field; full discovered
ECU scan with explicit per-ECU success/failure/not-attempted coverage. The F48
validation should provide meaningful data and explain any remaining unavailable
fields, without promoting one vehicle's result to universal support.

## Phase 4 — history and coding reads

These can be independent research lanes once identity/variant selection exists:

- **History:** trace SHM read action through libraries/PRG interpreter into every
  send buffer; distinguish local `.bmwsh` serialization and job arguments from
  on-wire records. Establish NBT read first, then CIC/EVO/MGU independently,
  including pagination, dates, distance, dealer/items and unknown field retention.
  A routine named add/write cannot become the read path without byte evidence.
- **Coding:** trace reference ECU/software/CAFD matching and actual current coded
  data reads. Separate definitions from live values, recover NCD/block ordering,
  encoding/compression/integrity and preset masks/multi-field composition.
  Easy and advanced screens must use the same verified underlying values.

Use `enet-sim.json`, `sim-enet.json`, named F/G/I simulations and Link's
`sim-u-series.json` only as labelled offline examples, never hardware proof.

Outputs: rewritten docs 11/12, relevant corrections in 02/04/06/08/13/16,
operation contracts and per-variant capability matrix. Exit: genuine read-only
flows and exact live state for every enabled history/coding page.

## Phase 5 — mutations, backup, readback and recovery

Only after read contracts exist, recover add/edit/delete/replace history,
coding writes and diagnostic clearing separately. Trace security/session
requirements and modern signed/authorized coding restrictions; do not infer
write permission from static flags or probe keys/bypasses.

Design shared durable baseline/intended/observed files with VIN, ECU/software,
raw state, schema version and integrity; all coding/history writes save backup
first. Fault clearing retains the owner's explicit no-report exception. ACK or
positive SID alone is insufficient: reread, compare and report mismatches or
uncertain outcomes. After interruption, reread/compare before user-selected
recovery; never automatically replay an append. Keep local preview distinct
from vehicle restoration. Specify cancellation and multi-ECU partial outcomes.

Exit: complete encoder/readback contract per mutation, supported recovery and
owner-approved behavior for still-open product decisions, followed by scoped
implementation PRs and owner-operated validation.

## Phase 6 — broaden coverage and prepare releases

Build a support matrix by transport/gateway/ECU/software/feature using branches
recovered from sources. For each row distinguish source-evidenced,
implemented, offline-inspected, physically validated, unsupported and unknown.
Compare coverage with the reference apps; explicitly retain their limitations.
Add ISTA+ if existing sources leave concrete diagnostics/topology/MIL/CBS gaps;
inventory the supplied version/data dependencies before planning its engine.
CBS remains future scope ([existing task](future-cbs-research.md)). ISTA+
availability is not a prerequisite for exploiting current APK/PRG material.

Validate interface behavior and packaged asset closure on macOS/Windows,
supported runtimes and offline launch. Full Ruff lint, Ruff format and mypy
are required before each push; green static checks do not establish car behavior.
Physical validation currently covers only the owner's car, so fleet validation
gaps remain explicit even when static source support is broad.

## Delivery order and acceptance

1. Analysis capability + evidence inventory.
2. ECU discovery/identity, then vehicle information + complete DTC reads.
3. History and coding reads, so all requested pages can load real data.
4. Verified mutations and recovery.
5. Broader source coverage and platform releases.

Each package ends with retained evidence, corrected specs, implementation plan,
an isolated PR when implemented, gate results and stated validation limits.
Do not complete a package on class-name search, UI resemblance or mock success.
Before UI implementation, resolve only the pending owner decisions it needs:
DTC status/clear scope, MIL semantics, multiple-car selection, history editing
rules and recovery presentation (doc 21). No further car session is required
to start source analysis.

## Planning verification

This documentation change was prepared on `codex/rea-protocol-recovery-plan`
from merged main `c866f83`. The complete 688-line session was inspected, its
request/reply counts and SHA-256 checked, and an identical local preservation
copy made outside Git. The four original artifact hashes above were rechecked;
existing extracted-source entry points were inspected without target execution.
Fresh REA doctor output establishes the listed setup gaps, not decompilation.

Full `scripts/preflight.sh` passed: Ruff lint, Ruff formatting and mypy across
all 18 application files. Local document links and `git diff --check` passed.
No app code, automated suite, vehicle operation, binary execution, provider
installation or host MCP configuration change was performed. The plan's phases
remain pending; these checks validate the planning deliverable only.
