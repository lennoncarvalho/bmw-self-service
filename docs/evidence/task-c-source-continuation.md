# Task C continuation — D94 reconciliation and native execution

2026-11-05, after PR 20 merged at `3b491244e563d2ffb0edee8b371743b855065fd7`.
Authority: **primary implementation references** and **observed locally** controlled
execution. No physical vehicle request/reset. The paired
[evidence JSON](task-c-source-continuation.json) retains exact hashes, PRG
offsets/tables, managed MVIDs/tokens/IL anchors and verification scope.

## Corrected source boundary

`D94` abbreviates the engine variant `D94BX7A0`, canonical group `G_MOTOR`,
address `0x12`, CBS 6.3. Its PRG is absent from the canonical 4.29 ECU directory,
but **is available** at `sources/Ecu/D94BX7A0.prg`, 6,457,109 bytes, SHA-256
`98a5f17ebfe99e73b998ed029ae11e650452d19a930ec546fb035fe95ae55a0c`.
That is exactly the historical artifact hash; blanket source-absence statements
are superseded. It is not relabelled a canonical 4.29 file.

The [explicit supplement contract](task-c-supplemental-jobs.json) lets development
bundle generation include this file with a pinned hash. Supplements cannot
replace canonical names, duplicate another supplement, or remain unreachable
from the selected groups/dependencies. Paths are absolute or repository-relative,
independent of the launch directory. Bad input leaves the previous bundle intact.
The runtime manifest keeps canonical missing files separate from supplemental
provenance. No automatic scan/fallback to the old source directory was restored.
The app still uses only generated assets, never research paths or REA.

There are now 48 bundled CBS readers: 47 canonical and one supplement, with
40 primary roles and eight observational branches. All 531 bundled PRG/GRP files
load. Canonical group entries lacking files remain 94; the supplement reduces
generated-bundle missing jobs to 93. The five non-CBS missing USES files remain
explicit; D94 has no USES dependency.

## Recovered read and reset behavior

- `CBS_DATEN_LESEN` at `0x23c108` sends `22 1001`. CBS 6.3 uses `ID_CBS_MESS`
  and already-scaled remaining/forecast kilometres, unlike the older named
  result layout. Its time forecast field is `FRC_INT_T_CBS_MESS`. Counter250
  and day31 are valid. Invalid units, availability, dates and sentinels remain
  unknown. This PRG emits distance as signed 16-bit scaled results; records that
  overflow those results remain explicitly unknown, with raw bytes retained,
  rather than displaying a wrapped number or scaling it a second time.
- `SVK_LESEN` at `0x15c30` emits `22 F101`; the exact software reply is retained
  and rechecked before mutation. The native reader, source hash, primary role,
  item table and software/before state must match. Missing/mismatched native
  jobs cannot activate the old handwritten routine fallback.
- `CBS_RESET` at `0x219880`: `STR;0x{item};standard` encodes
  `31 01 1000 {item} 02 FF FF FF`. `CBS_6_3_KENNUNG` defines 24 user service
  identifiers; `E0/E1/FF` remain excluded. The start reply must be exactly
  `71 01 1000 {general} {component} {reserved2}`. Both application codes must
  be zero before continuing. A four-byte start acknowledgement is insufficient.
- Current managed `CBS_Reset_NEW`, token `0x06000012`, explicitly selects
  D94/G_MOTOR and calls `RRR`. Its Sleep(1000) at IL `0x21e8` reaches the D94
  check at `0x2216` through switch state128; state130 then branches into the
  RRR preparation at `0x1ef8`, with D94 call at `0x1f8c`. The app waits that
  second under the existing 30-second deadline, then executes the native `RRR`
  job once: `31 03 1000`, exact eight-byte `71 03 1000` result and zero
  application codes required. A lost/rejected query remains uncertain.
- Both occurrences, identity/software/before checks, journal writes, settle and
  post-read stay inside one protocol-owner operation. There is no automatic
  replay. Response-confirmed completion remains distinct from observed post-state.
  The old start-only 6.3 interpretation is superseded.

The canonical managed module asks for `STATUS_CBS_DATEN_LESEN` in some D94
branches, while this historical PRG exposes `CBS_DATEN_LESEN`. The integration
uses the actually executed, hash-bound reader; it does not invent the missing
alias or claim that the mixed source collections are one release.

## Observation-owner investigation

Revisited every supplied Testmodule DLL containing both `CBS_RESET` and a
candidate observation-name substring: eight candidates, including the additional
transport/delivery and correction callers. REA member inspection retains complete
CIL coverage and separately disclosed string coverage; tokens remain build-local.
The paired JSON includes the examined methods/offsets and candidate dispositions.

The CMEDIA substring leads resolve to `CMEDIAR` or its embedded telephone
configuration, not the exact CMEDIA variant. In `ABL_DIT_AS6100_TRAMODE_RESET`,
the DME8FF_L literals are `Diverse` calls to `STEUERN` and
`_STEUERN_LESEMODUS_FVVM`; BCP_SP21 literals are `Powermanagement` reads.
Those do not establish a primary standard-CBS reset route. The existing main
workflow still selects the right engine and cluster/DSC owners.

BCP_SP21, CMEDIA, DME8FF_L, EHC_01, GSGE01QW, LMV_01, MGU_02_A and S63TU_L0
therefore remain readable observations with resets blocked. This bounded
investigation does not prove a universal hardware restriction or exhaust
dynamically selected routes. No ownership grant was invented.

## Verification and review

Retained one-off checks, results and visually inspected Qt screenshots:
`/Users/lennon/BMW-Tool/investigations/task-c-continuation-20261105/`.

| Boundary | Observed result |
|---|---|
| Native readers | All 48 × 22 baseline vectors pass; D94 adds exhaustive byte-field/boundary coverage for 1,824 total D94 vectors, 2,858 unique vectors overall |
| Source encoders/software | All 778 item encoders and 48 software request readers pass; encoder presence alone grants no ownership |
| Native loading | All 531 assets load; three malformed directory cases refused |
| D94 workers | 18 completion/error scenarios; four storage failures around the two mutation occurrences; actual 1s delay, deadline exhaustion and cancellation checked |
| Worker regression | Existing 121 scenarios pass |
| Actual protocol owner | 10 fragmented HSFZ/Scapy/udsoncan/native-job loopbacks, including D94 pending, lost-result and session-refusal cases; source-folder access forbidden by audit |
| Actual Qt | D94 manual read/reset confirmation/cancel/power, loading/navigation lockout, automatic reread, stale/failed refresh, uncertain-result lockout and existing DSC/read-only/DEMO flows pass |
| Build/compiler | Out-of-repository launch, exact copy/hashes, canonical override/duplicate/mismatch refusal, original-bundle preservation and byte-identical contract regeneration pass |
| Full app gate | Ruff check, Ruff format check and mypy pass over all 52 files; changed development scripts also pass scoped Ruff checks |

The independent reviewer found the working-directory dependency and source
result-delay omission. Both were fixed and specifically rechecked; no remaining
actionable issue was reported in this increment. This is not an independent
audit of every unchanged application module.

Local execution used Python 3.15.2, not target 3.13. No automated suite or `tests/`
directory was added. Physical owner-F48 acceptance remains unperformed; retain
[the existing read-first procedure](task-c-cbs-reliability.md#owner-f48-acceptance-procedure).
DoIP CBS mappings and Windows/package acceptance remain outside this milestone.
