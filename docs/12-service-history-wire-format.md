# Service history formats and unresolved execution contracts

Current Task B behavior (2026-10-29): [spec 26](26-feature-readiness-spec.md)
and D-21–D-49 in [doc 21](21-product-decisions.md) supersede conflicting older
examples below. No write Cancel; disruptive controls/normal quit blocked during
writes. Completion is operation/cycle-aware, not universally immediate readback.
History add may preserve/rewrite the complete list; reject future/same-day new
entries; use entered mileage without reading current odometer. Mac Python-source
functionality is the milestone; packages/signing are deferred. Protocol examples
remain unverified unless linked to retained source evidence.


Reviewed 2026-10-28. The earlier “fully resolved” claim contradicted its own
examples. This is the current research contract, not an encoder specification.
Original text remains in Git history.

## Current primary evidence and implementation

The [deep native/PRG investigation](evidence/task-b-history-deep-investigation.md)
supersedes earlier unverified byte-layout claims. CIC/NBT/NBTEVO/HU_MGU ADD jobs
encode `31 01 A0 81`, a 19-byte fixed header (seven-byte ASCII dealer field),
then up to thirteen eight-byte items. Year, mileage, remaining distance/time
are big-endian; remaining distance is signed32. The implemented reply shape is
`71 01 A0 81 result` with a checked application result. Extra response bytes
fail closed; the source status extraction alone does not prove their absence. These constants are
routine identifiers, not DIDs. PRG arguments are not sent as ASCII job text.

`app/service_history.py` implements the recovered codec and result validation.
It does not send to a car. The supplied local .bmwsh records share this body
layout; their eight records round-trip byte-for-byte. This does not establish
a genuine vehicle read, fresh original state, append preservation or restore.
Unknown existing data is preserved locally, with new-entry validation separate.

## Still unresolved

No complete maintenance-history read has been recovered. `31 01 A0 81` is ADD,
not a read. The Lite reader UI is an unconditional Pro message; extended native
tracing has not confirmed a dormant reader behind a key. A separate Pro build
is a possible source, not a proven requirement. Ten headunit PRG inventories
and their generic selectors supply no recovered list reader. The actual CBS
history22 1004 on other ECUs is a different store and cannot substitute for it.

Execution/session prerequisites, complete preservation/capacity, activation and
ignition semantics still require evidence. Never erase as a discovery probe or
use imported file bytes as proof of a complete current car baseline.

## Required application behavior

Before history mutation, retain an identified complete baseline and durable
backup/intent. Follow D-29's operation-specific completion/cycle rules rather
than universally requiring immediate same-cycle readback. Validate application
status and distinguish response-confirmed from observed verification. Resolve
uncertain/partial outcomes before retry or recovery; no automatic replay.

The initial feature requires read/add; edit/delete/replace and CBS remain later.
Reject future and same-day additions, allow backdated entries and entered
mileage, support multiple items and free dealer input within real field limits.
No Cancel during definitive writes. See [spec26](26-feature-readiness-spec.md)
and [owner decisions](21-product-decisions.md). Backend sync remains unproven.
