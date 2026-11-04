# Current-source CBS jobs — 2026-11-04

Authority: static PRG tables/comments/listings and controlled offline execution
of those jobs in the embedded native interpreter. No reference application was
executed and no physical vehicle traffic occurred. Exact artifact hashes,
source job offsets, source tables and runtime contract fields are in
[source contract](source-cbs-current-jobs-20261104.json).

REA independently inspected CIL members of supplied
`Testmodule/ABL_GEN_AS6100_CBS_RESET.dll` (SHA-256
`c87b8440abb90e8dc9d79f5e32d00598f304b4f8e950d217d8269b475695f2db`),
parent `ev_d17bfe8339598b52f4c2b052e47d2a93b0679834bf61c83ac0a4e63ae7a876b7`,
summary `ev_424b46b78b8f5abd99581f75af93d6e81e8c1d536ba903925ad38c436f9c73ce`.
This cross-reference identifies the orchestration artifact, not proof of a live
reset. The actual encoders/decoders below come from the current PRGs.

## KOMBSP21 CBS7.0

The restored PRG disproves the old asset's CBS6.3/no-reset disposition. It has
`STATUS_CBS_DATEN_LESEN` explicitly for CBS7.0, and `CBS_RESET` with STR/RRR.

- Read: `22 10 01`, whole12-byte records. The job returns renamed fields such as
  `ID_CBS_MESS`, `RMMI_CBS`, `AVAI_CBS`, and already-scaled forecast/year results.
  The runtime consumes those job results rather than treating a2027year as an
  offset from2000 or multiplying an already-scaled forecast a second time.
- `TAB_RESET_ART` defines `0x02 / standard / Standardreset`.
- Start job args `STR;0x<ID>;standard` emit
  `31 01 10 00 <ID> 02 FF FF FF`; source requires exact`71 01 10 00`.
  This only confirms start, not final reset completion.
- Results job args `RRR` emit `31 03 10 00`; source requires eight-byte
  `71 03 10 00 <general> <component> <reserve2>`. Only zero general/component
  codes establish completion. Source-defined refusal codes remain rejection;
  unknown/unavailable codes remain uncertain.
- Frozen intent includes both requests, args, source hash and before-record.
  The exact generated job hash is required for reset. Identity/before checks,
  start/results and after-read run in one owner operation. Source job retry
  loops cannot resend a mutation; no automatic resume/replay.

## DSC_25 conditional extra sequence

The older app's plain-write guard is retained when extra side effects were not
acknowledged. With acknowledgement and the exact source job, the source's SVK
and fixed-record test choose the plain or extra path. Before the first mutation,
source rereads must exactly match the prechecked SVK/CBS bytes.

The extra source path is:

1. The selected CBS `2E 1001` record.
2. `86 00 02` (stop event reporting).
3. `31 01 03 04 00` (ECU routine0304).
4. `14 FF FF FF` (clear all DSC fault memory).
5. The same selected CBS `2E 1001` record again.
6. `86 05 02` (restart event reporting).

The second identical reset is a source-planned occurrence, not a transport retry.
The job boundary uses an ordered occurrence list; the same bytes at any other
position are refused. Each granted request has a durable sending event before
transmission and a checked outcome after. The full possible sequence, side
effects, source gate and job hash exist in the intent before any car request.
Interrupted outcomes do not run a cleanup/retry automatically.

The PRG itself checks the response SID for the control steps. The app additionally
requires86's control-type echo, routine0304's RID echo and exact54/6E1001 for
clear/reset, followed by the job's successful status and a separate after-read.
Only exact860002/860502 are permitted by the adapter grant; no event registration,
periodic data or generic86 request is enabled.

The UI must explicitly acknowledge that this branch may clear DSC faults, pause
and restart event reporting, invoke routine0304 and send two planned resets.
No fault-restore or counter-rollback promise is made. An interrupted sequence may
leave event reporting paused or fault memory cleared; inspect retained outcomes
before any new operation.

## Verification

Retained one-off scripts/results:
`~/BMW-Tool/investigations/source-job-assets-20261104/`.
Actual native PRGs were used with synthetic replies, not simulated Python jobs.

- CBS7.0 read fields, verified reset/post-state, start rejection, malformed start
  (no results request), lost results, application rejection, unavailable result
  code and one-shot worker replay rejection.
- DSC full extra and plain paths, no-ack extra zero-send, changed source software
  zero-send, first-reset rejection, interrupted event-stop with no later sends,
  and out-of-position repeat rejection. All mutations remained under the owner
  callback and each had durable intent/sending evidence first.
- Existing DME_BX8/KOMB25/DSC_I1 jobs still execute read/fault jobs from generated
  assets with original sources inaccessible. D94's6.3 routine was already
  implemented; its original PRG is absent from the current release, so no new
  D94 artifact validation is claimed.

Reproduce the generated CBS asset with:

```bash
.venv/bin/python3 scripts/recover_cbs_definitions.py \
  docs/evidence/task-b-cbs-contract.json \
  coding_data/diagnostic_catalog.json.gz coding_data/cbs_definitions.json \
  --current-contract docs/evidence/source-cbs-current-jobs-20261104.json
```

No tests/ suite or physical reset was performed. Source support is not physical
validation across all ECU software versions.

## Whole-release reconciliation and ownership

The companion provenance audit reconciles every original definition against the
restored canonical PRGs:23 byte-identical,20 changed,1 unavailable (D94). It
records47 current CBS readers and14 native reply vectors for each (658 runs),
including units, calendar/count, availability, forecast sentinels and status.
After the documented normalization corrections no field mismatches remain.
Original hashes remain in the older evidence; current hashes and complete
listing fingerprints describe only the current artifacts. D94 retains its
historical identity without claiming a restored matching PRG.

New reader rows BCP_SP21,IB_I20,KOMB_J29 and MGU_02_A are retained as observations.
Read response ownership alone never enables a write. The reset application's
G_KOMBI/G_MOTOR/G_DSC routes and explicit variant routes establish40 primary
rows;8 other source readers remain visible with an explicit unrecovered-owner
reason. The companion JSON records each row's source group, role and capability.
Unavailable/copy readers do not block a unique proved primary writer; competing
proved primaries remain ambiguous. Plan execution revalidates these roles against
the generated contract instead of trusting the display record.

After the native signed-width correction, fresh CBS7 and DSC worker outcome
checks and existing native fault/CBS jobs passed again. These are offline source
and byte/error checks, with no physical reset or universal vehicle claim.
