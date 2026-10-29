# Service history formats and unresolved execution contracts

Current Task B behavior (2026-10-29): [spec 26](26-feature-readiness-spec.md)
and D-21–D-55 in [doc 21](21-product-decisions.md) supersede conflicting older
examples below. No write Cancel; disruptive controls/normal quit blocked during
writes. Completion is operation/cycle-aware, not universally immediate readback.
History uses ADD-only or explicit acknowledged replacement; reject future and
known-local same-day entries; use entered mileage without reading current odometer. Mac Python-source
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

## Product scope and remaining execution facts

The owner has retired history read/retrieval research under D-50. No complete
reader was recovered in the inspected sources; this is not a universal statement
about all possible BMW access. Do not require read/backup/readback before enabling
an otherwise reviewed history writer. CBS remains a separate later feature.

[Workflow28](28-service-history-workflow.md) is the current product/data/UI
contract: local **JSON only**, multi-item cards, one-entry ADD without ERASE, or
explicit acknowledged ERASE followed by the reviewed full replacement list.
Source .bmwsh/.tst formats remain research-only; no product adapters are planned.
The local file parser currently in app/service_history.py is an implementation
artifact to retire from the runtime API, not a promised import feature.

Identify the headunit and exact encoder, durably save local project/intent/raw
request plan with prior vehicle history null, then validate each final business
result. Retain activation instructions and distinguish response-confirmed from
observed verification. No automatic replay/resume/rollback or guaranteed restore
of unreadable original history. Coding still requires full original ECU data.

Session prerequisites, ADD-only capacity/order behavior, ERASE result handling
and reset/ignition completion still need exact source/vehicle validation; never
erase as a discovery probe or automatically fall back to replacement on rejection.
Future and known-local same-day rules and the sourced fourteen-type service list
are in workflow 28. Unknown old car dates cannot be checked by this app.
