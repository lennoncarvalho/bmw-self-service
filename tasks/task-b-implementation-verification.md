# Task B implementation slice — verification and handoff

2026-10-29, `codex/task-b-feature-recovery`, based on `origin/main` db3c99f,
with the approved Task B planning commits carried over. **Task B remains open.**

## Implemented and reviewed

- Fundamental REA/source reconstruction rule in AGENTS.md; exact provenance,
  contracts and unresolved breadth in
  [the recovered contract record](../docs/evidence/task-b-recovered-contracts.md).
- Full discovery observation window, multiple-vehicle refusal, alternate
  source-backed HSFZ VIN endpoint and live-gateway/unverified-VIN troubleshooting.
- Recovered gateway inventory and variant IDs; discarded the F000 text parser,
  F18A integration level and other guessed optional information reads.
- Reproducible compressed diagnostic catalog: 1,307 mappings; 225,815 English
  normal/information fault descriptions, with missing source assets explicit.
- Fault, information and permanent memory reads with per-target coverage;
  correct UDS status names. Clear All tracks application reply and post-read
  separately, preserves uncertain outcomes and stops sends on lost transport.
- Lazy page batches; five-minute diagnostic/coding batch budgets and at most
  30-second individual requests; no partial initial page publication.
- Definitive-clear warning, progress, navigation/close/disconnect/Cancel lockout,
  and wait for competing reads before the clear begins.
- Exact F101 coding snapshot reads from all declared groups; unchanged identity
  checked before publishing a complete durable snapshot. No first-file CAFD
  selection in this reader and no editable synthesized live presets.
- Version1 ordinary JSON backups, immutable-original integrity, separate intent
  and observations, durable atomic preparation, portable import/export, corruption
  display and explicit deletion. No advertised vehicle restore action.
- Old guessed coding/history encoders blocked at worker boundary. History form
  future-date picker limit and same-day duplicate prevention; live add still
  blocked until a complete original-history read/encoder is recovered.

## Independent review

The owner explicitly requested an outsider reviewer. An independent agent loaded
project review/protocol/Qt skills, independently recovered source evidence, then
reviewed the actual diff. Concrete findings repaired:

1. Qt workers had two deletion owners after disconnect: explicit main-window
   retirement ownership now prevents deleted-C++-object access in the reap timer.
2. Lost connection during a clear was swallowed: loss handling is deferred until
   clear outcome presentation and replayed when mutation lockout ends.
3. Ambiguous clear outcomes lost their classification: `outcome-uncertain` is
   retained instead of relabelled as an unavailable read.
4. Dead-owner VIN setup could appear as limited connected: dead owner now fails
   setup; limited troubleshooting requires a still-open owner.
5. Fault-memory helper accepted wrong SID/subfunction or truncated data: exact
   echo/alignment validation added before the standard decoder.
6. Already-running coding reads could interleave with clearing: lazy page loads,
   current-worker guards and the pre-commit competing-read gate cover this path.
7. Snapshot runtime errors left loading forever: settled English error delivery
   and exact-current-worker guards added.

Final reviewer disposition: no blocking findings in the reviewed slice. This is
not a review approval of unimplemented history/preset/restore/MIL features.

## Verification performed

- Full `scripts/preflight.sh`: Ruff lint, Ruff format check and mypy all green
  over `app/`, `ui/`, `main.py` (32 source files after new modules).
- Catalog regenerated directly from SHA-checked original APK; decoded object
  identical to independently derived data. Shipped gzip SHA-256
  `c988392c26b75e57551139b6cd82662befad808112025d568908348837bb44ab`.
- One-off offline replay of actual packaged simulations: gateway inventory has
  33 distinct addresses; F101 parser decoded 26 CAFD identities on 13 ECUs with
  positive responses. Negative simulation replies were excluded as negatives,
  not passed to a positive decoder. These are source examples, not car captures.
- One-off offline boundary exercises: normal/information/both permanent layouts,
  malformed positive echoes and truncation rejection, exact catalog counts,
  JSON prepare/state append/export/import equality and modified-original rejection.
- Independent offline Qt retirement reproduction passes after fix. Independent
  coding snapshot check read all 13 source-declared groups, including system,
  CAF_ID and signature groups, plus two F101 reads into a temporary durable file.
- Final deadline check confirms shrinking per-request budgets and no sends after
  diagnostic/coding batch expiry; DoIP optional-info branch sends no guessed
  byte-addressed requests.
- Offscreen Qt DEMO source launch, diagnostic/backups render, navigation/close/
  Cancel lockout, and clean shutdown passed. Screenshots visually inspected at
  `/tmp/task-b-diagnostics.png` and `/tmp/task-b-backups.png`.
- `git diff --check` and changed-document local-link checks passed before push.

No `tests/` directory or automated suite was created. Offline exercises were
one-off temporary scripts and do not substitute for owner-operated acceptance.
Local runtime is Python3.15.2 on macOS, with the repository's3.13 static target;
no3.13 execution, live car traffic, fault clear, history/coding write, restore,
network reconfiguration, packaging, signing or Windows validation was performed.

## Material evidence and remaining blockers

Native SHM read case3 routes to a Pro-only message, matching the bundled help;
all four PRG inventories lack a recovered history read job. A source/capture
containing the genuine history read is needed before backup/preserving add.
Do not infer it from `.bmwsh` local serialization or destructive Lite rewrites.

Native read-action REA bundle SHA-256
`4f78ceafb6b9a84317a16338a8a1c457c3f06d16182e1faefc877cbe37f02066`;
help PDF SHA-256
`753636ec8469d62da83bc8efbff8aa4fdde34f7b601510e7aa9b3dde53902db9`.
The contract record includes exact event method/jump/string coordinates.

Complete preset predicates/dynamic types, composed writes, authorization,
restoration/ignition semantics and power checks still need implementation.
Real MIL and DoIP inventory/address mapping remain unrecovered. The APK also
omits 156 unique UDS description assets. Remaining requirements stay open in
spec26/task checklist; source recovery breadth is not physical all-BMW proof.

Deliver this as a **draft PR for the reviewed recovery slice**, with no claim of
Task B completion. Owner acceptance on the Mac/car remains required for the
current milestone; Windows/packages remain explicitly later.

## History codecs and runtime follow-up — 2026-10-29

Extended REA/Delphi tracing covers four forms, PE resources/imports, Buy/erase
handlers, native fixed-slot record parsing and all direct callers of the common
ENET exchange. No key-only reader activation was confirmed; indirect-call and
alternative networking limits remain explicit. Four primary and six additional
headunit PRGs plus 861 diagnostic JSON assets were reviewed for actual history
reads. CBS6.3 history is a different store, not a complete headunit baseline.

Independent review verified app/service_history.py and the actual360-bytefile:
8records, exact byte-for-byte roundtrip. A separately assembled golden PDU checks
all fixed offsets, BE year/mileage, signed distance and unsigned time. One-off
checks cover new-entry future/same-day, integer limits, seven-byte dealer and
1..13 item bounds; unknown original flags/statuses/nonASCII/padding/14items;
stale original+changed model rejection; trailing/truncated/invalid-calendar
input; all known and unknown final result statuses/echoes. Final reply extensions
fail closed rather than being interpreted without evidence. No blocking codec
review findings remained. No vehicle I/O path was enabled or exercised.

Runtime audit:32 pre-existing modules/requirements/packaging contain no REA
invocation/dependency; offscreen source startup loaded no research tools. The
new33rd module has only standard-library imports. Misleading source-tool and
unproven security-level commentary was removed; AES material correctly labeled
128-bit. AGENTS.md explicitly makes REA development-only, including code/data
recovery, and forbids a runtime tool/service dependency.

Full Ruff lint, Ruff format and mypy passed across33app/UI/main files. No
suite/tests directory, car execution/write, source EXE execution, license
modification or additional physical acceptance is claimed. Retained report and
script hashes are in docs/evidence/task-b-history-deep-manifest.json. Complete
Task B and its history reader/execution requirements remain open; PR stays draft.
