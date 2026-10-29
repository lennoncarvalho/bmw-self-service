# Task B — vehicle order and remaining identity branches

2026-10-29. PR14 verified merged at dcb70a604a9bbe1958410497eedcfe6a6c4d854c
(19:06:05Z). Clean worktree; fetched origin and created
`codex/task-b-vehicle-order` from origin/main. No merged branch is reused.

## Concrete increment plan

1. Recover S-02 gateway3F06 packed vehicle order: request, response boundary,
   six-bit alphabet, fixed fields, optional section markers and termination.
   Correct historical FA/XML/build-date assumptions before implementation.
2. Add bounded standalone `app/vehicle_order.py`, preserving raw bytes and
   decoded field/section availability. Integrate only the source HSFZ branch in
   the existing settled PostConnectWorker batch. No extra session or writes.
3. Display model range, type key, time criterion, paint/upholstery and decoded
   options honestly; time criterion is not an observed production date.
   Investigate U/I metadata and exact model lookup independently; never select
   transport or enable coding from model/category alone.
4. Independently trace remaining MIL readers; enable only recovered complete
   source contracts and account for every remaining definition.
5. Exercise byte boundaries/negatives/unknown sections, settled refresh/reset,
   DEMO and Qt rendering. Independent Python/Qt/protocol review and corrections;
   full app preflight before push. Record remaining source paths and deliver PR.

No vehicle requests, new fleet access, history readers, legacy adapters, guessed
DoIP mapping or coding baseline changes are part of this increment. Source
support/offline verification and physical observations remain separate.
