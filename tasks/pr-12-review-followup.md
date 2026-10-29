# PR #12 review follow-up

Reviewed against `cdd03bd74eb5d1bc541273453004761c0856fac2` on
2026-10-28. Scope: validate the 12 inline comments and the review-body suite
suggestion, repair valid remaining defects, then reply and resolve each thread.
The PR is open; this work stays on its existing implementation branch.

## Plan / affected files

Change `app/protocol/facade.py` to perform at most one due session keepalive
per idle pass, letting the owner check queued work between ECUs. Preserve
serialization and fail-closed recovery after ambiguous transport failures.
Record verification here; no dependency, protocol mapping or test-suite change.

## Comment dispositions

| Comment IDs | Assessment / action |
|-------------|---------------------|
| 4407136324, 4407136329, 4407136334, 4407136344, 4407136351, 4407136355 | Invalid premise: OperationContext uses plain `@dataclass`; only the other DTOs are frozen. Fresh Python 3.13 metadata and deadline/cancellation assignments confirm mutation works. No frozen-dataclass workaround is warranted. |
| 4407136362 | Valid distinction, already repaired by 89cd94c: a correlated final TesterPresent NRC disables maintenance for the affected ECU and preserves the connection. Timeouts/EOF/unowned responses must still close the stream; swallowing those errors would break late-response ownership. Recheck both full transport facades offline. |
| 4407136372 | Partly valid: one idle pass could service every due ECU, delaying newly queued work by multiple keepalive budgets. Limit each pass to one maintenance exchange and recheck the owner queue before the next ECU. The suggested independent socket reader conflicts with spec 25. |
| 4407136374 | Already repaired by 89cd94c: strict ASCII/printability validation now converts unsupported binary I-level data into a friendly unavailable reason. Keeping errors="ignore" would invent a partial value. |
| 4407136379, 4407136385 | Accepted pinned boundary rather than a current defect: both calls reuse the exact doipclient 1.2.2 source/wheel recorded in the manifest. A patch update cannot occur under that exact pin; a version change must revalidate this private helper. Source inspection confirms its bounded eight-byte header serialization; no competing header implementation is added. |
| 4407136387 | Already repaired by 89cd94c: time is imported at module scope. |
| Review-body suite suggestion | Not adopted: AGENTS.md and D-10 explicitly prohibit an automated suite. Use the authorized full-app gate and one-off offline exercises. |

## Verification

Observed locally on Python 3.13.18: a queued operation ran after the first
maintenance exchange and before the second due ECU. Both existing full-facade
rejected-TesterPresent exercises passed, preserving subsequent reads.
OperationContext metadata reports frozen=False and deadline/cancellation
assignments succeed. Full Ruff lint, Ruff formatting and mypy passed across all
28 app sources; a separate Python 3.13 mypy run also passed. No vehicle requests or network setup are part of this
review follow-up. Physical/platform/release acceptance remains as recorded in
the Task A verification document.

## CodeRabbit follow-up

Reviewed CodeRabbit review 5692170550 against `dad94a5`. Both actionable
inline findings are valid and were reproduced locally on Python 3.13.18:

- 4408128345 (`app/protocol/doip.py`): with only an AliveCheckRequest queued,
  prepare answered it and then timed out waiting for another message. The
  diagnostic request remained unsent. Make the idle/pre-send poll consume one
  frame while keeping active response waits able to dispatch multiple controls.
- 4408128352 (`app/protocol/facade.py`): POLICY, INVALID and UNSUPPORTED outcomes
  all raised ConnectionError. Preserve PermissionError for policy and ValueError
  for invalid/unsupported outcomes; keep timeout/cancel/uncertain behavior.

Verification after edits: one-off socket/bridge alive-check sequences, classified
exception mapping, both full transport exercises and the full app static gate.
No automated suite or dependency change is planned. The summary's optional
docstring/test generation controls are not instructions to run a generator or
override the owner's no-suite policy; document the changed receive semantics.

CodeRabbit verification observed locally: the lone alive check returns from
prepare with diagnostic sent=False, and an actual udsoncan bridge subsequently
sends/receives VIN while handling alive checks before send, during ACK wait and
during final-response wait. Policy/invalid/unsupported map to their intended
exception classes; timeout/cancel/uncertain mappings are unchanged. Both full
transport facade exercises passed with explicit PermissionError expectations.
Full Ruff lint, formatting and mypy pass over 28 sources; separate Python 3.13
mypy also passes. These are offline observations, not new vehicle validation.
