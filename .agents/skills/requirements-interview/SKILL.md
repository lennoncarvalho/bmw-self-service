---
name: requirements-interview
description: Interview the owner about BMW Self Service feature behavior and acceptance criteria without filling unresolved product decisions with assumptions.
---

# Requirements interview

Read `docs/21-product-decisions.md` and known vehicle context before asking.
Work through a few related questions at a time, using concrete scenarios and
consequences. Record answers as owner decisions with dates; keep proposals and
unanswered questions separate. Resolve facts from code/artifacts or primary
documentation rather than asking the owner to invent protocol details.

Prioritize: connection/partial identity; supported vs validated vehicles;
write backup and readback; interruption and recovery; diagnostic clearing/MIL;
service-history append/edit/erase and CBS separation; easy/advanced applicability;
languages, units and error behavior; release acceptance and validation resources.

Ask what the app should show or do on success, unavailable data, partial failure,
cancel and reconnect. Test requirements against a realistic failure, such as a
write acknowledged just before Ethernet disconnects. Do not assume an operation
can safely be repeated. Avoid asking again about an answered choice.

Persist decisions before deriving implementation tasks. Continue independent
audit/setup work while answers are pending. Do not turn an unanswered question
or silence into approval, or require another approval for routine work already
authorized by the user.
