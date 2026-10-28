# Task A specification — standard protocol library migration

Status: ready for implementation planning. This task changes protocol plumbing;
it does not supply the missing BMW operation definitions. Companion task:
[implementation checklist](../tasks/protocol-library-migration.md).
Task B's feature contract is [doc 26](26-feature-readiness-spec.md).

## Required result

Replace duplicated standard UDS service logic with udsoncan and integrate
selected maintained Ethernet transports behind one project-owned API. Preserve
the verified F48 HSFZ/session/VIN behavior, explicit partial-data results,
read-only enforcement, logging and transaction/recovery guarantees. Keep Qt
Widgets, CarWorker/QThread and synchronous calls; no asyncio migration.

The source and version decision is in [doc 24](24-protocol-library-evaluation.md).
Start with udsoncan 1.26.1, Scapy 2.8.0 HSFZ and doipclient 1.2.2. Pin only
versions actually integrated. Gallia is a comparison fallback, not an additional
mandatory dependency. If a candidate cannot meet this contract through a small
adapter, record exact evidence and propose an upstream fix or alternative;
do not silently retain a second complete protocol stack or rewrite the library.
GPL-compatible distribution is accepted (D-15); record the chosen app license
and required dependency notices/source materials before distribution.

## Ownership and API contract

One active connection owns its socket, receive stream and request scheduling.
One serialized diagnostic operation includes address selection, session state,
send/ACK, pending replies and the final response. Keepalive uses that same
owner; GUI workers must not read the socket independently. Different ECUs have
separate session/timing/capability state even when sharing one gateway socket.

Separate these responsibilities:

| Boundary | Owner / required behavior |
|----------|---------------------------|
| UDP discovery and transport activation | Transport adapter; selected interface/IP, validated entity identity and explicit transport |
| Raw diagnostic send/receive | HSFZ/DoIP adapter; complete frame parsing, control dispatch, source/target filtering and lifecycle |
| Standard UDS request/response | udsoncan service/client layer; echoes, NRCs, pending semantics and typed standard results |
| BMW selection and codecs | Task B's evidence-backed operation registry keyed by gateway/ECU/software/data version |
| Application policy | Connection facade; read-only check before every send, cancellation, outer deadline, outcome and logs |
| UI integration | CarWorker threads emit result/progress/error; GUI consumes explicit states only |

The transport interface must expose lifecycle, target identity and raw payload
send/receive with a supplied absolute monotonic deadline. The diagnostic facade
must expose a serialized request operation with ECU identity, request payload,
deadline/cancellation context and correlated response or classified failure.
Retain a compatibility facade for current `send_uds(ecu, payload, timeout)`
callers only while migrating them; convert timeout to one deadline at entry.
Typed service entry points are preferred for supported standard operations.
Choose exact class names during the task's implementation plan.

Do not put udsoncan Client over today's blocking request-and-response
`send_uds`: its transport connection expects send and receive separately.
Assign NRC 78/UDS parsing to one layer rather than maintaining two independent
dispatchers. A candidate backend does not become a second socket consumer.

## Invariants the migration must preserve

1. A default 30-second operation budget covers queueing, activation where part
   of that operation, send, ACK, complete fragments, pending replies and receive.
   Bound connection discovery/setup and every optional operation explicitly.
   Library response timers do not replace this outer deadline.
2. A timeout/cancel retains outstanding-request identity. Before reuse, resolve
   its late response or invalidate/reconnect; never reset a partial stream or
   discard bytes to make the next request appear clean. SIDs/DIDs alone cannot
   distinguish repeated identical late requests without lifecycle ownership.
3. Validate endpoints, positive/negative SID, supported echoes, body lengths
   and reasonable frame-size bounds. Dispatch ACK/NACK/alive/control traffic
   independently. An ACK is not a successful diagnostic or vehicle mutation.
4. Disable doipclient automatic reconnect/resend. Failed/uncertain mutations
   are not replayed; transport replacement cannot bypass Task B recovery.
5. Read-only policy checks actual bytes at the final diagnostic send boundary,
   including generic/raw service APIs. Permit only the existing evidenced
   read/session/TesterPresent allowlist; no unverified routine probes.
6. Keep source interface/IP binding, no root for ordinary diagnostics, no
   automatic DHCP/address changes during read-only operation. Do not enable
   Scapy endpoint scans or source-example writes as migration verification.
7. Keep raw discovery/transport bytes, control frames and UDS payloads with
   connection/request IDs, ECU endpoints, durations, outcomes and tracebacks.
   Library logger output supplements rather than replaces the current capture.
8. Shutdown/cancel settles owned workers and sockets; stale results cannot
   populate a new connection. Preserve DEMO isolation and disabled live
   history/coding guards until Task B supplies real contracts.

## Known integration boundaries

Resolve each observed issue in doc 24: udsoncan queue cleanup and post-send
response timer; doipclient wall-clock timers, ACK wait, target selection,
idle alive service and optional resend; Scapy control returns, source binding
and send-error return value. Record whether handled by adapter, upstream
change or candidate rejection. Do not mark these resolved by library import.

`BaseConnection.empty_rxqueue` must not forget an unfinished transaction.
No-op cleanup is also insufficient if stale replies remain unaccounted for.
Keep negative/invalid/unexpected response exceptions enabled and convert them
to structured outcomes; do not recreate FA's empty-success bug.

## Files and implementation sequence

Expected edits: `requirements.txt`, `app/connection.py`, `app/uds.py`,
`app/worker.py`, `app/mock_connection.py`, `ui/main_window.py` and affected
diagnostic callers. Add a narrowly scoped protocol-adapter module/package if
needed; record its exact paths before implementation. Keep vehicle codecs and
write encoders out of this migration. Update packaging/data notices and docs
15/24/25 when dependency selection is final.

Work in order: document ownership/API → udsoncan service integration → HSFZ
adapter → DoIP adapter → worker/UI compatibility → remove superseded loops →
verification/packaging. Use separate reviewable commits or PRs where necessary;
each new implementation branch starts from current main, never a merged branch.

## Acceptance

- Selected releases pinned, hashes/metadata recorded, optional CAN/raw-capture
  dependencies excluded unless actually needed; no blanket import of a
  scanner/framework or source application at app startup.
- Every protocol responsibility has one owner and every known integration
  boundary has a reviewed disposition. No GUI-thread I/O or event-loop mixing.
- Manually inspect/replay local recorded bytes at a clearly declared boundary:
  ACK then response, fragmented frames, negative replies, pending, late reply,
  wrong endpoint/echo, EOF, cancellation and reconnect. Use supplied/offline
  evidence; do not create an automated suite or `tests/`.
- A read-only owner-operated F48 run again discovers, opens session and reads
  VIN. Preserve partial coverage and explain unsupported fields. DoIP requires
  separate source/offline validation; F48 HSFZ does not validate DoIP hardware.
- Full Ruff lint, Ruff format and mypy pass; verify target Python 3.13 imports
  and macOS/Windows package closure, recording platform checks still unavailable.

Task A is not complete merely because imports/static gates pass. If physical
validation awaits the owner, report implementation/offline readiness and leave
that acceptance item pending. Completing Task A does not mean DTCs/history/
coding work end to end: those are Task B deliverables.
