# Task C continuation after PR 20

Base: PR 20 merged as `3b491244e563d2ffb0edee8b371743b855065fd7`.
Branch: `codex/task-c-source-completion`. Owner authorized implementation and a PR.

## Verified starting boundary

`D94BX7A0.prg` is present in `sources/Ecu/`, SHA-256
`98a5f17ebfe99e73b998ed029ae11e650452d19a930ec546fb035fe95ae55a0c`,
matching the historical definition. It is absent from the canonical 4.29 ECU
directory and generated bundle. Earlier blanket source-absence statements are
superseded by this observation. Availability alone does not enable a reset.

## Plan and acceptance

1. Recover the available D94 reader, standard-reset encoder, software reader,
   result decoder, dependencies and current managed workflow selection. Compare
   source/native results, including malformed and negative responses.
2. Revisit the eight observation owners against supplied orchestration/callers.
   Implement only established primary routes; retain exact unresolved evidence.
3. Extend development bundle generation with explicit, hash-bound supplemental
   jobs that cannot replace canonical files. Compile recovered contracts and
   regenerate standalone assets; no runtime source lookup.
4. Integrate native D94 execution under the existing owner, frozen identity,
   software/before checks, journal, exact mutation grants and no-replay policy.
   Preserve contract-specific completion rather than assume CBS7 behavior.
5. Exercise source/native, worker/error, protocol-owner and Qt boundaries with
   one-off local checks, request independent review, correct findings, and run
   full preflight. Update current task/spec/evidence status and open a new PR.

Physical acceptance remains separate. No car traffic or service reset is
authorized by this development task. Request targeted owner logs only at a
concrete blocker that those logs can resolve.

## Delivered continuation

Steps 1–5 are implemented and verified. See
[source, behavior and verification](../docs/evidence/task-c-source-continuation.md)
and its paired JSON. The source matrix now counts 47 canonical readers plus one
explicitly supplemental D94 reader, 40 usable primary roles and eight observations.
No new reset role was assigned after the expanded caller investigation.

Changed implementation: `app/cbs.py`, three development asset producers,
generated CBS definitions/runtime manifest, a hash-bound supplement contract,
and task/spec/evidence/handoff files. No new dependency, runtime source lookup,
native interpreter modification or physical vehicle operation.

Independent review found two issues: relative supplement paths depended on the
launch directory, and the result query omitted the managed source's one-second
delay. Both were fixed and independently rechecked. The wait stays inside the
existing overall deadline/owner operation and stops on interruption or an
insufficient remaining budget. Full preflight and focused verification passed.
