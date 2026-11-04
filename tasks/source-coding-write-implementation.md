# Source-backed coding execution — 2026-11-04

## Plan

Implement new `app/coding_write.py`, preserving the existing owner, CarWorker,
complete-baseline OperationStore schema and no-replay rules. The UI (root-owned)
selects source preset/option IDs, not request bytes. Preparation rereads F150/F101
and every group of every exact reported definition, composes masks through the
plain coding catalogue and finalizes source signatures. Confirmation receives an
immutable plan. Execution revalidates the same source composition, rereads VIN,
identity/software/baseline, durably journals each send/result, and runs source
sessions/authentication/group writes/CPS/reset/clear under one owner operation.
Restore is separately prepared from validated originals and fresh reads.
No runtime research source access, car traffic, automated suite or Git mutation.

Source recovery coordinated with root and coding_source_recovery: F101 CAFD role5,
BTLD role6; group reads are direct22DID; complete signature rules/keys come from
the recovered database helpers, not guessed XOR fields. Finalizer availability
and exact signatures are required; missing contracts are concrete source work.

## Implemented execution and review fixes

- Added immutable `CodingPlan`, prepare/write/explicit-restore workers. Selection
  inputs are source definition/preset/option IDs. Preparation reads fresh F150,
  F101, every complete exact group and a second F101 under the sole owner.
  Each read has a 30-second cap within the 300-second preparation budget.
- F101 selects role5 CAFD and role6 BTLD; duplicate/unknown bootloader identity
  refuses authorization. All selected presets must belong to the source primary
  definition, not an arbitrary reported secondary catalogue root. Source dynamic
  presets resolve against the same baseline before composing their actual masks.
- Source predicates run at preparation and execution. ID8 comes from the recovered
  exact-definition/live-byte helper. Category-conditioned choices read gateway
  3F06, decode the actual model range, map it through generated source metadata,
  freeze its raw bytes and compare again before mutation. Caller category zero
  cannot bypass this source predicate. Unrestricted options need no extra FA read.
- Source signing is the `s0.A` **non-null current baseline** branch `k.a.i`.
  The CIC/j and 300C/l branches are guarded by a **null baseline** in source and
  are not substituted for this flow. Fresh-baseline restore also uses branch i.
  All definition groups and source signing keys are required; wrong signature or
  group widths fail before confirmation. E-series XOR metadata is not used.
- Exact source group ordering retained. `s0.P` excludes DME/address12 group3010;
  no selected change to that omitted group can be accepted by preparation,
  plan validation or program dispatch. Other targets with source ECU metadata
  `partialCodingAllowed` write differing groups only (`s0.O`); missing/false
  metadata retains the source full-group path. Comparison uses exact bytes,
  avoiding the source Java hash-code collision weakness.
- Execution publishes complete original/intended OperationStore data before any
  send, then journals sending and raw outcomes per step. It rechecks source
  composition, VIN, exact source-identified ECU/name/address index, software and
  all baseline groups under one exclusive owner callback before sessions/writes.
- Source sequence: 1001/1003/1041, exact bootloader seed/key, group writes,
  keepalive/signature-check delay, VIN-last7 stamp37FE, reset (address50 uses
  default session) and Clear DTCs. Standard typed session calls preserve library
  timing negotiation; only source27 requests need the exact raw service grant.
  Keepalive uses the standard correlated 3E00 instead of source suppressed3E80,
  so the one-owner dispatcher continues to own every possible response.
- Whole execution budget600seconds includes queueing; each request caps30seconds.
  No mutation Cancel, automatic retries or uncertain-outcome rollback. A checked
  definite rejection may restore only known accepted changes after fresh identity/
  current-byte comparison proves the expected transition. Reset/disconnect,
  malformed completion or persistence failure stops all sends and closes the
  connection; in-memory evidence remains available through the root UI.
- Explicit restore is separately prepared from validated live originals and fresh
  current reads, with its original identity/hash frozen into the plan. Changing
  plan mode alone cannot turn preset editing into arbitrary raw restoration.

## Meaningful offline verification

One-off harness retained outside the repository at
`/Users/lennon/BMW-Tool/investigations/source-coding-execution-20261104/` uses the
actual KOMB25 `00000760-007-003-017` definition, actual AS/NCDS source entries,
source RSA signing/composition, and a fake serialized owner with synthetic ECU
bytes (not physical observations). Checks pass:

- Normal coding and separately prepared restore, 96 exchanges together after
  source partial-group selection; complete originals survive unchanged in JSON.
- One-shot worker guard and exact UDS seed/key service round-trip.
- Reset disconnection becomes uncertain/closed with no automatic restoration.
- Definite second-group rejection restores only after rereading expected accepted
  current bytes; recorded original groups are preserved.
- Read-only mode and known insufficient power cause zero sends.
- Tampered option token fails before any vehicle send.
- Changed current bytes stop before a coding mutation.
- Disk failure after an accepted write retains the raw6E response in memory,
  closes the session and sends no next group/reset.

Ruff checks on new files and full app mypy pass at this checkpoint. Root owns
final complete preflight, visual/UI checks and independent review; no push,
PR or physical validation performed by this subtask.

### Final recovery/predicate review additions

- Combined-definition function lookup and all-option mandatory-function checks
  now use the source loader's combined-definition APIs; dynamic options are
  resolved before concrete patches.
- Preparation scans owned, validated prior live coding records on the worker.
  Unresolved writing/partial/uncertain/mismatch operations carry path/id/hash,
  last state and fresh current-vs-original/intended comparison into the plan.
  Matches are observations, never inferred cycle failure or automatic resolution.
- Write/restore require `recovery_acknowledged` when prior records exist. The
  exclusive owner rescans before the first diagnostic send and refuses newly
  unresolved/changed records after confirmation; deletions do not fabricate
  evidence or automatically restore anything.
- Extended one-off checks pass: prior comparison/mandatory acknowledgement,
  interruption created after confirmation (zero sends), and mode-flipped restore
  missing its bound original provenance (rejected).

### Recovered source definition selector (follow-up)

REA recovered `k.q.b(k.v)`: the APK first uses its exact packaged definition;
otherwise it selects the immediately lower patch with the same ID/major/minor.
This is an evidenced source rule, not an arbitrary nearest-version alias. The
loader now applies that selector even when an exact trimmed ISTA XML is present,
retaining the exact XML as a group-bound/signature cross-check where available.
Conflicting exact source metadata has an explicit disposition, never a silent
combination of old names and different new positions.

The engine preserves reported F101 identities while freezing each source
`definition_resolution` (reported/selected/method/material hashes/cross-check)
and revalidating it before mutation. Its existing definition digest binds the
actual selected material; the curated root hash is separately frozen as
`preset_source_sha256`. All reads, group validation, masks and signing resolve
through the same selected source layout. Duplicate preset names use the actual
root `preset_index`/`source_index`; a name alone is accepted only if unique.

A second one-off harness uses actual ENTRYNAV reported
`00000DED-003-015-037`, source-selected named `003-015-006`, F150 `0F1BE0`, and
source exact-XML widths/signature metadata. Synthetic current bytes and the real
source key/definition helpers pass preparation and writing of the ordinary
`VOLUME_POPUP_DISPLAY / ACTIVE` preset. It confirms that the reported identity is
unchanged, selected-layout tampering is rejected, and the two `VOL_MAX_ON` root
entries retain distinct indexed identities. This is offline source-contract
verification, not a physical result or observation of the fixture BTLD/ECU pair.

### Actual source critical-condition guard — implementation plan

Root REA recovered the source address120-only sticky critical-condition guard
(19020C, fault IDs801225/801224) and its per-VIN producer. Add a generic executor
in `app/coding_guards.py`, driven by compiled selection metadata, and separate
bounded non-restorable evidence files under coding-guards. Preparation checks
existing sticky state, reads and persists the actual observation before review;
execution requires that prepared record and refetches before mutation. Corrupt
records or a missing prepared record fail closed. First use has no cache in the
source, so it must establish and persist a fresh observation rather than guess.

### Critical guard result

Added compiled-contract execution and non-restorable sticky observation storage
in `app/coding_guards.py`, integrated into prepare/write/restore. Source evidence,
first-use/missing-record distinction and offline error checks are in
`docs/evidence/source-coding-critical-guard-20261104.md`. Fresh VIN precedes any
per-VIN observation; blocked notices name the ECU and journal the actual no-write
outcome rather than generic post-cycle instructions. Root owns final compiled
asset publication and UI checks.


Final compiled-asset guard check uses actual IHKA definition
`000016EE-113-100-006`, source F150 index `78 0F1D70`, the compiled guard contract
and synthetic current bytes. It passes full preparation/writing with two checked
guard reads, then separately verifies a critical condition appearing after
confirmation blocks every coding write, persists the sticky fact, names IHKA_F15,
and stores the same precise instructions in the operation journal. Subsequent
preparation remains blocked without reinterpreting empty fault memory as recovery.
The normal sourcecoding/restore harness now makes96 exchanges including the added
fresh preparation VIN reads. Retained scripts/output are outside the repository.

## Source coding-read prerequisites increment

Recover and compile the outer `s0.r` reader prerequisites before enabling headunit
coding reads: source FSC retrieval/storage/verification first, then exact NBTEVO
integration-level/RAM/HMI refusal. Add a bounded standalone reader-contract asset
and `app/coding_prerequisites.py`; wire snapshots, preparation and final execution.
Keep FSC material separate from complete ECU coding baselines. Preserve read-only
mode (1042 and routine31 remain refused), atomic local durability, one protocol
owner and fresh checks before coding. Verify request order, offsets, refusal and
cleanup offline; no vehicle traffic and no test suite.

Implemented outer reader prerequisites in `app/coding_prerequisites.py`, called
by snapshots, preparation and execution before complete coding-group reads.
The source branch retrieves FSC files with 1003/1042/31010F1F04 and per-item0B,
publishes exact returned payload bytes atomically, verifies the two source RSA
public moduli for variant0F2230, and always attempts checked1001 cleanup. FSC
files are separate local entitlement material, never complete ECU coding backups.
Execution checks prepared file hashes and source contract, fresh identity and the
current source list before coding. Read-only sessions remain zero-send refused.
Snapshot/preparation acquire disruptive-action lockout through an acknowledged GUI
signal before source sessions. NBTEVO checks retain first-block/unpadded I-level,
exact21-byte response, signed32-bit RAM offset12, and ID5-prefix threshold.

Offline retained `/Users/lennon/BMW-Tool/investigations/source-coding-reader-20261104/`:
request order, exact FSC bytes, existing file reuse, frozen file integrity refusal,
critical integration-level refusal, signed-memory refusal, readonlyzero-send all
passed. The prior full engine exercise also passed complete signed coding/restore,
rollback, uncertain disconnect, disk-after-acceptance, fresh baseline, plan tamper,
prior-interruption acknowledgement/race and boundrestore checks. No vehicle or
universal physical validation is claimed. Full preflight passed after integration.
