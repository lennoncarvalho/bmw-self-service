# Task C — CBS reliability evidence and verification

Date: 2026-11-05. Authority: **primary implementation references** from supplied
managed modules/PRG jobs and **observed locally** controlled native execution,
fragmented loopback HSFZ and actual Qt workers. No physical vehicle operation.
The [complete matrix](task-c-cbs-reliability.json) retains each exact variant,
address, version, role, reader/reset offsets, current SHA-256, table identifiers,
item policy, dependencies and verification counts. Historical hashes remain in
the original contracts and the 2026-11-04 provenance audit.

## Selection and remaining source branches

Recount: 48 runtime definitions, 47 current PRGs, one absent historical D94.
There are 40 primary roles including historical D94, hence 39 current primary
roles and eight observation-only branches. Native encoder availability is
separate from authority to reset a service item. Every current CBS PRG matches
its bundled copy byte for byte; none has an absent USES dependency. The complete
release still has 94 missing group-table job files and five missing USES files;
that is not a CBS-wide missing-dependency claim.

REA retained the main orchestration's complete CIL members at
`ev_d17bfe8339598b52f4c2b052e47d2a93b0679834bf61c83ac0a4e63ae7a876b7`:
`ABL_GEN_AS6100_CBS_RESET.dll`, SHA-256
`c87b8440abb90e8dc9d79f5e32d00598f304b4f8e950d217d8269b475695f2db`,
version 4.29.12.23381, MVID `a0cc540b-847c-45a4-9447-d3f1bd30cfc4`.
The matrix includes build-local tokens and IL offsets for
`CBS_Daten_Lesen_NEW` (`0x0600000a`), `SG_Gruppen_NEW` (`0x0600000b`),
`CBS_Reset_NEW` (`0x06000012`) and `Überprüfung_CBS_Reset_NEW` (`0x06000013`).
These recover G_KOMBI/G_MOTOR/G_DSC selection and explicit new variants.

The 34 supplied CBS-named modules were inventoried. Focused REA inspection also
covered the WAR reset workflow, return-code decoder, motor correction workflow
and delivery workflow; full artifact identities/MVIDs are in the matrix.
The motor correction module, SHA-256
`d72f0e7e0b9ae89867b7493bc08b03edd1518a7ac2c98364c924ec4651762914`,
has a G_MOTOR2 **fault read**, while its correction writes target G_MOTOR.
It does not establish a left-controller standard reset. The delivery module's
telephone literal is **CMEDIAR**, not an exact CMEDIA reset-owner match.
Its transport/delivery and KWP operations are not substituted for this task.

| Observation | Current group | Disposition |
|---|---|---|
| BCP_SP21 | G_ZGW | CBS7 reader and encoder recovered; no primary service-reset route established |
| CMEDIA | G_TEL | Readable observation; delivery telephone matches do not establish a standard reset owner |
| DME8FF_L | G_MOTOR2 | Main workflow selects DME8FF_R; correction module's left-controller fault read adds no reset authority |
| EHC_01 | G_EHC | Readable observation; no primary route established in the examined CBS workflow |
| GSGE01QW | G_EGS | Readable observation; no primary route established in the examined CBS workflow |
| LMV_01 | G_LMV | Readable observation; no primary route established in the examined CBS workflow |
| MGU_02_A | G_MMI | CBS7 reader/encoder recovered; no primary service-reset route established |
| S63TU_L0 | G_MOTOR2 | Main workflow selects S63TU_R0; correction-module investigation adds no left reset authority |

These restrictions describe the established current workflow. They are **not**
proof that every such controller is universally a read-only mirror. No new
primary branch was invented to eliminate an unchecked ownership claim.
`D94BX7A0` is listed by the group table but its PRG is absent from the restored
release and generated bundle. Its historical decoder remains usable for labelled
reads; missing current software/item contracts prevent reset confirmation.
No current D94 job execution or restored-release support is claimed.

## Recovered defects and integration

- The native loader discarded all tables when the directory exceeded 1,000.
  BCP_SP21 actually contains 1,844. A size-checked directory with the existing
  development reader's 20,000-table ceiling replaces that silent loss. Rebuilt
  universal arm64/x86_64 library; source job bytes are unchanged. BCP's documented
  standard arguments now execute correctly offline. Ownership remains blocked.
- CBS7 supports day 31 and service count 250. CBS5 jobs can expose an invalid
  raw `FF` counter as numeric 31; the normalized display now keeps it unavailable.
  Impossible calendar combinations remain explicit unknowns. Status text and
  distance/time forecasts are displayed without rescaling already-scaled values.
  Malformed/unaligned responses and unaccounted native result records fail closed.
- Generated definitions carry actual per-variant reset identifiers and the
  source `SVK_LESEN` request, verified in all 47 current PRGs as `22 F1 01`.
  Explicit CBS reads retain software response bytes. Invalid availability/count,
  unknown item identifiers, duplicate primary records, mismatched jobs, missing
  required CBS7 jobs or software cannot authorize a reset. A failed observation does not disable a
  unique proved primary merely because the observation is unreadable.
- The confirmation freezes the exact definition hash, software and before-record.
  The source-required default session is restored only if another session is
  active, with checked `10 01` completion and a journal event. No security access
  or guessed additional routine is introduced. Identity/software/before checks,
  native execution, settle and post-read run inside one owner operation.
- Nested owner calls previously replaced the native callback's context with the
  outer one, losing its transmission flags. Each child now retains actual send
  facts while inheriting the outer deadline/cancellation/correlation. Aggregate
  mutation state is returned to the same owner. A real loopback exposed this;
  direct fake-connection checks alone did not.
- CBS7 still requires checked STR **and** RRR completion. DSC retains its exact
  planned sequence, two reset occurrences and disclosed fault-clear/event-control
  side effects. An unavailable optional DSC job permits only the already-guarded
  plain branch. Pending, malformed and unknown results never become success or
  definitive rejection merely because a start was acknowledged.
- Reads/resets use the foreground backdrop, block competing actions, and retain
  prior rows while loading. Failed refreshes preserve stale values and revoke
  reset selections. Outcomes remain visible independently of refresh failures.
  Stale callbacks, read-only, DEMO and transport restrictions explain refusal.
  An uncertain outcome or journal failure blocks further resets in the session
  until reconnect/read. No mutation is automatically replayed.

## Offline verification

Retained scripts, raw results and screenshots:
`/Users/lennon/BMW-Tool/investigations/task-c-20261105/`.
REA's exported ten-record bundle is `rea-evidence-final.json`; the matrix retains
its SHA-256. It includes readable CIL plus the reported string terminal-flag
coverage limitations; no managed assembly was loaded or executed.

| Check | Observed result |
|---|---|
| Native CBS readers | 47 × 22 vectors = 1,034, zero normalized-field mismatches; includes original 658 vectors |
| Native item encoders | 754 variant/item combinations, including observational encoders; DSC ordered branches checked separately |
| Native software readers | All 47 emit exactly `22 F1 01` |
| Native asset loading | All 530 PRG/GRP assets load; three malformed table directories refused |
| Actual reset workers/native jobs | 121 scenarios: completion, unchanged/lost post-state, changed variant/software/before, duplicate/malformed/absent values, no replay, negative/lost start/results, and storage failure before/after each mutation occurrence |
| Additional zero-send guards | Power failure, read-only, VIN mismatch, wrong transport, closed connection; mismatched job hashes disable reset |
| Real protocol owner | Seven fragmented loopback scenarios through Scapy/udsoncan/native jobs: default, CBS7 and DSC with pending replies, lost results, pending deadline exhaustion, extended-to-default session, and refused session with zero writes |
| Runtime source separation | Loopback file-access audit rejects source-folder, encrypted-package and reference-parser access |
| Actual Qt flow | Manual read/expansion/refresh, native reset workers, cancel/power/DSC confirmation, backdrop/resize/navigation/timer lockout, stale/read-only/DEMO refusal, failed refresh retention, and uncertain-result lockout |
| Quality gate | Full Ruff check, Ruff format check and mypy over app/ui/main; 52 Python files. Local Python 3.15.2, not a Python 3.13 validation |

The source oracles and real-owner checks are independent verification boundaries.
A separate diff-review pass checked ordering, mutation occurrence accounting,
result publication, stale callbacks and parser bounds. No second human/agent
review, physical acceptance, Windows/package validation or PR is claimed.

## Owner-F48 acceptance procedure

1. Use the normal source launch in read-only mode first; explicitly read CBS after
   connection. Record the actual F150 identities at the cluster, engine and DSC.
   Match KOMB25/DME_BX8/DSC_I1 only if actually reported; historical observations
   are not a replacement for current identity. Check all available records against
   the vehicle's service display, including units/date/count and unavailable data.
2. Retain the read bytes, exact source hashes/software and complete coverage.
   Expansion must perform no I/O; refresh must be exclusive and expose failures.
3. Only for an appropriate service that the owner separately authorizes: reconnect
   in normal mode, read again, inspect the single-item confirmation and power
   acknowledgement, and acknowledge any disclosed controller side effects.
   A preflight/storage/identity failure must send no reset.
4. Retain before, application responses, local journal and observed post-state.
   Distinguish response-confirmed from verified. If the car needs its documented
   cycle/reconnect, perform that before drawing a post-state conclusion; no fixed
   universal ignition-cycle rule is asserted. An uncertain or partial outcome
   requires inspection/reconnection, never a gratuitous test reset or replay.

Physical acceptance remains unperformed. Another vehicle is not a development
dependency and these checks do not certify every ECU/software combination.
