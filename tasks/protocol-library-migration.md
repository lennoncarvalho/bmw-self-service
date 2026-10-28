# Task A — migrate standard protocols to libraries

Status: implementation plan recorded on 2026-10-28; migration has not started.
Spec: [doc 25](../docs/25-library-migration-spec.md).
Evaluation and artifact hashes: [doc 24](../docs/24-protocol-library-evaluation.md).
Next task: [Task B — REA feature recovery](rea-protocol-recovery.md).

Execution checklist: [Task A development tasks](protocol-library-migration-tasks.md).

## Planning baseline and scope

Observed locally: clean `main` and fetched `origin/main` both pointed to
`4898b0a8586aa1e41236775356895c6375096a2b` (merged PR #10). This plan was
created on `codex/task-a-library-migration-plan` from that revision. This is a
documentation branch. After its merge, start app changes on a fresh `codex/`
branch from current main; do not reuse this branch or a merged implementation
branch. Recheck caller locations and library identities against that base.

Read `AGENTS.md`, `SESSION-PROMPT.md`, docs 19–25 and the Python/BMW protocol
skills. Inspect the current checkout and PR state; preserve other work. Create
a fresh `codex/` implementation branch from current main. Follow the design and
ordered tasks below before switching live traffic. Consult original library
source, not REA, for ordinary open-source library behavior.
Use [doc 27](../docs/27-rea-source-guide.md) when
a BMW-specific uncertainty requires source-app evidence.

Deliver one transport/service API, preserving the retained F48 HSFZ/session/VIN
baseline, partial outcomes, logging, read-only policy and DEMO isolation. Task B
owns BMW inventory, DID/codecs, history/coding encoders and product changes.
Migrating a call does not certify its current guessed mapping. In particular,
do not turn rejected FA/mileage/voltage requests or binary F18A into valid data.

## Current caller and ownership map

Locations below are observations of the planning revision, not proposed APIs.

| Existing path / entry points | Migration obligation |
|------------------------------|----------------------|
| `app/connection.py`: HSFZConnection/DoIPConnection, send_uds, _read_response, _keepalive, disconnect | Replace the two complete transaction loops with the owner, connector and selected adapters. Preserve fragments, late-response identity, controls and trace IDs. |
| `app/connection.py`: list_interfaces_detailed, discover_zgw, discover_doip_vehicle, _bind_to_interface | Carry the selected interface/local IPv4 and validated discovery identity into TCP. Current TCP constructors do not bind locally; DoIP discovery ignores its interface argument. |
| `ui/main_window.py`: _connect_real.do_connect, _read_ilevel, _read_fa, _read_mileage, _read_battery, _read_svt | Setup currently calls HSFZ discovery for both transports and selects TCP by series. Replace that plumbing with explicit validated discovery results; preserve the picker while treating series as a hint. Keep optional failures separate from connection identity. |
| `app/worker.py`: CarWorker, ConnectWorker, PostConnectWorker, KeepAliveWorker | Pass operation/cancellation context, separate result delivery from QThread lifecycle, and route all live I/O to one owner. KeepAliveWorker currently competes for the same lock. |
| `ui/main_window.py`: _on_worker_result, _on_disconnect, _retire_worker, _reap_workers | Replace GUI calls to potentially locking disconnect with nonblocking close requests. Ignore stale results by connection generation; retain workers through real completion. |
| `ui/diagnostics_page.py`: DtcReadWorker, ClearWorker, _on_clear_single | Use typed session/DTC services and preserve per-ECU partial results. The legacy single-clear handler calls send_uds on the GUI; remove that route under the existing one-Clear-All decision, without implementing Task B's clear/readback workflow. |
| `app/security.py`: request_seed/send_key; `ui/coding_page.py`: _load_coding_presets, CodingReadWorker/CodingWriteWorker | Audit compatibility consumers, including currently guarded/unused code. Preserve disabled live coding; do not activate probes, security algorithms or old encoders. |
| `ui/service_history_page.py`: read/write/erase workers | Preserve live history guards. Route any retained compatibility calls through the owner without validating their unsupported wire contracts. |
| `app/mock_connection.py`; `ui/vehicle_page.py`: load_data | Keep canned responses/local state separate from sockets. VehiclePage's direct calls are currently in its DEMO branch; do not mistake them for live I/O or use fixtures as vehicle evidence. |
| `app/uds.py` | Remove unused framing/parser/NRC duplication after callers migrate. Standard encoding/interpretation belongs to udsoncan; BMW decoding remains outside this layer. |

## Planned files and dependency direction

New application files, to be created only during implementation:

| Path | Responsibility |
|------|----------------|
| `app/protocol/__init__.py` | Narrow package exports; no socket creation, scans or backend auto-initialization on import. |
| `app/protocol/contracts.py` | Typed discovery/endpoint identity, operation context, immutable replies/outcomes, transport protocol and failure metadata. |
| `app/protocol/owner.py` | ProtocolOwner command queue/state machine, per-ECU sessions/clients, scheduling, final send policy, cancellation and shutdown. No Qt widget references. |
| `app/protocol/udsoncan_connection.py` | BaseConnection bridge exposing separate send/receive to the chosen adapter under the active owner context. No independent UDS transaction loop. |
| `app/protocol/hsfz.py` | Scapy HSFZ framing/socket adapter, discovery, interface binding, bounded control dispatch and raw transport logs. |
| `app/protocol/doip.py` | doipclient adapter, discovery/activation, target addressing, bounded control/diagnostic dispatch and raw transport logs. |

Existing application edits: `app/connection.py` becomes the public connection
facade while retaining network-interface helpers; `app/uds.py` becomes the typed
UdsServices layer. `app/worker.py` adds ProtocolWorker(CarWorker), context and
lifecycle integration. Update `app/mock_connection.py`, `ui/main_window.py`,
`ui/diagnostics_page.py` and compatibility consumers identified above, including
`app/security.py`, `ui/coding_page.py`, `ui/service_history_page.py` and
`ui/vehicle_page.py` only where necessary. `main.py` needs changes only for
protocol/version logging or lifecycle integration; no new UI flow is planned.

Dependency edits: `requirements.txt` only when each candidate is integrated;
`pyproject.toml` only for justified typing configuration, never broad exclusions.
Record actual distributions/hashes in `docs/evidence/protocol-library-inventory.json`.
Add `THIRD_PARTY_NOTICES.md` and selected dependency texts under `licenses/`
when selection is final. Record the exact app license in `LICENSE` only after
the owner selects it; D-15 accepts compatibility, not a specific license.
Update packaging commands in `README.md` and `AGENTS.md` if resource collection
changes, with runtime/dependency status in doc 15. Verify dynamically loaded
Scapy/udsoncan modules and legal materials are included in actual bundles.

Dependencies flow from UI/feature workers to the connection facade and contracts,
then to the owner/service bridge/adapters. Contracts have no Qt/backend imports.
ProtocolWorker runs the owner loop and does not import the facade at runtime;
remove worker.py's current concrete-transport import to avoid a cycle. Backend
instances, sockets and mutable udsoncan clients are private to that worker.

## Concrete API and execution model

Names below are the planned project API. A1 records any necessary refinement
before dependent code is written. Third-party objects do not escape to pages.

| API / value | Contract |
|-------------|----------|
| DiscoveryResult / ConnectionConfig | Explicit transport, gateway identity/IP, local interface/IPv4, discovery provenance and validated addresses. Never infer support from a series letter or truncate DoIP addresses to HSFZ width. |
| EcuIdentity / EcuSession | Connection generation, transport address, known variant/software identity, session and P2/P2* state. Unknown variant fields remain unknown; state is per ECU. |
| OperationContext | Operation/request IDs, absolute monotonic deadline, cancellation Event, connection generation and send/mutation phase. Create at submission, before queueing. Child requests consume the same deadline. |
| DiagnosticConnection.submit_operation(ecu, operation, context=...) | Return an OperationHandle immediately after queueing. GUI callers only submit/cancel/consume queued signals; the handle carries completion and cancellation identity. |
| DiagnosticConnection.run_operation(ecu, operation, context=...) | Worker-only submit-and-wait for one complete service sequence. The operation receives owner-bound UdsServices and never accesses widgets. |
| DiagnosticConnection.request(ecu, payload, context=...) | One generic request through that same queue, policy and client, returning correlated raw UDS plus classified outcome. Supported standard services use udsoncan; unsupported extensions require an explicit service definition. |
| UdsServices | Typed change_session, read_data_by_identifier, read_dtcs, clear_dtcs and tester_present. Preserve raw bytes beside decoded standard results. A successful clear response is protocol acceptance; Task B owns state verification and the multi-ECU workflow. |
| TransportAdapter | discover/open/activate, send_diagnostic, receive_diagnostic, service_control and close, each bounded by context. Return addressed complete diagnostic envelopes; never consume NRC 78 as a second UDS lifecycle. |
| request_close / cancel | Thread-safe queue/Event changes only at GUI entry. The owner settles I/O and closes sockets; lifecycle completion is asynchronous. |
| send_uds(ecu, payload, timeout=30.0) | Temporary compatibility facade, callable from workers only for live traffic. Reuse an enclosing operation context; otherwise create one deadline at entry. Return the complete raw UDS reply, including a correlated final negative reply for existing callers, with failed outcome metadata/logging. Transport/timeout/cancel failures raise project exceptions. Remove it after all consumers have an explicit disposition. |

Within the owner thread, services and nested compatibility calls execute inline
under the active context; they never enqueue and wait on their own queue. Each
command completes its handle on success, failure or shutdown. Signal delivery
to UI slots must use the receiver's GUI context and immutable result data.

Task B supplies immutable operation/codec registrations keyed by exact
gateway/ECU/software and definition version/hash. UdsServices accepts the resolved
DidCodec/service configuration as an owner-applied snapshot before an operation;
reject conflicting or missing registrations for typed decoding. Task A provides
this extension boundary and the evidenced VIN codec, not a new BMW dataset or
mutable global codec registry. Generic compatibility can retain undecoded bytes
without presenting a guessed interpretation as a typed success.

One ProtocolWorker(CarWorker) is the sole live socket/client executor. Existing
feature workers can enqueue a multi-request operation and wait off the GUI;
they do not call backend objects. The owner processes one complete operation at
a time, including session selection, send/ACK, pending and final response.
Keepalive is scheduled in the same owner loop, including idle transport control
service; retire the separate socket-reading KeepAliveWorker. Separate QThread's
native finished() lifecycle from result_ready(object), updating all consumers
and worker reaping together rather than relying on the currently shadowed signal.

Use bounded receive/poll slices to inspect cancellation without extending the
deadline. Never depend on a queued Qt cancel slot being delivered during a
blocking owner operation. Wake the queue on close; settle queued callers with
cancelled/connection-closed outcomes, and retain the worker until native finish.

### Deadlines, sessions and stream recovery

- Ordinary operations default to 30 seconds for the entire submitted sequence,
  including queueing, session changes, sends, ACKs and all pending responses.
  A DTC batch uses explicitly documented per-ECU operations with aggregate
  progress/cancellation; the whole fleet scan is not silently one 30-second read.
- Read-only connection setup has one 30-second outer deadline: discovery,
  TCP and routing activation each use at most 5 seconds of the remainder;
  session/VIN share what remains. No step restarts the budget. Optional fields
  use separate declared budgets and cannot undo verified connection identity.
- Existing privileged network fallback and its 10/20-second waits are an
  unresolved network-setup concern in doc 21. Keep them outside this read-only
  validation path; do not redesign or exercise them during Task A. Record any
  affected non-read-only setup timing before changing that behavior.
- udsoncan owns standard SID/echo/NRC/pending/P2/P2* behavior. The bridge caps
  its post-send timer with the outer context. The owner tracks which operation
  owns every in-flight response and every partially received frame.
- After timeout/cancel following send, retain outstanding identity. Resolve a
  matching final late response under a bounded recovery context before reuse,
  or invalidate/close and require an explicit reconnect. Never send another
  identical request while the prior response could be mistaken for it. Only
  udsoncan handles pending/standard correlation, including during reconciliation.
- Track ready, active, recovery-required, closing and closed states explicitly.
  No new diagnostic operation starts in recovery-required. Malformed/unexpected
  traffic with unresolved ownership follows the same rule; a fully correlated
  final negative response ends the operation without disconnecting the car.
- Retain known per-ECU session timing; do not treat gateway-only TesterPresent
  as maintenance of every session. Configure the existing F48 heartbeat as a
  compatibility profile with its evidence limits recorded; establish control
  initiation/timing before changing it. Idle polling is not proof of liveness.

### Policy, outcomes and logs

Apply read-only policy to the actual encoded payload immediately before every
backend diagnostic send, including generic requests, compatibility calls,
session changes and TesterPresent. Keep the current service allowlist and exact
session/subfunction restrictions; it does not certify BMW-specific DIDs. Reject
empty/malformed payloads before indexing. Backend convenience methods must not
provide a path around this check. Do not add unverified routine/security probes.

Use immutable project outcomes with connection/operation/ECU identity, raw
response, optional decoded result, phase, failure kind and NRC where applicable.
Distinguish policy-blocked/unsupported, negative-response, invalid-response,
unexpected-response, transport-rejected, timeout, cancelled, connection-lost
and outcome-uncertain. A queued cancellation has sent nothing; cancellation or
loss after a mutation may have begun is uncertain. No automatic replay/retry.
No negative/invalid result becomes an empty successful optional field. Retain
complete/partial/not-attempted coverage at the feature level and existing live
history/coding guards. This layer does not label a write vehicle-verified.

Map project failures to user-friendly messages at worker/UI boundaries; retain
original exceptions/tracebacks in DEBUG logs. Preserve raw discovery, transport
fragments/frames, controls and UDS with connection/generation/request IDs,
endpoints, elapsed/remaining time and final outcome. Library logs supplement
these records. Raw captures stay local; shared reports omit vehicle identifiers.

## Candidate feasibility gates

Primary implementation references are the exact released wheels/source hashes
in doc 24's manifest, available locally under
`/Users/lennon/BMW-Tool/investigations/2026-10-28-protocol-libraries/`.
All dispositions below are requirements to demonstrate, not completed fixes.

| ID / candidate boundary | Required disposition before live selection |
|-------------------------|--------------------------------------------|
| U-01: empty_rxqueue before send | Check owner outstanding state; reconcile or invalidate before entry. No blind draining, partial-buffer reset or no-op that hides stale traffic. |
| U-02: response timer begins after send | Cap queue/send/ACK and every read with the original monotonic context; enable negative/invalid/unexpected exceptions. |
| U-03: legacy/raw services | Inventory 0x01/0x1A and other nonstandard callers. Use a small explicit udsoncan service extension where supported behavior must remain; no parallel NRC loop or guessed BMW codec. Unknown unsupported requests fail before send with a recorded reason. |
| H-01: constructors lack local bind | Prove a bounded prebound ordinary TCP socket can reuse Scapy framing/stream support via a small adapter or upstream extension. No root/raw capture requirement. |
| H-02: controls, fragmentation and bounds | Retain ACK/alive/error frames and all partial bytes, enforce length bounds before body allocation/read, handle coalesced frames and EOF. Scapy UDS wrapping alone is insufficient. |
| H-03: send failure returns zero | Convert failed/zero sends into a transport failure with correct sent/uncertain phase; never wait for a response to an unsent request. |
| H-04: control encoding | Compare diagnostic and type-specific control serialization to retained bytes; do not apply diagnostic address/length rules to every control or use Scapy's UDS parser as a second service layer. |
| D-01: auto reconnect/resend | Set auto_reconnect_tcp=False and inspect all reconnect paths; demonstrate zero implicit resend after failure. |
| D-02: wall-clock/resetting timeout | Bound actual socket waits with monotonic context even under unrelated ECU traffic. A wrapper timeout checked only after an unbounded library call is insufficient. |
| D-03: diagnostic reply before ACK | Preserve/queue the early reply while completing ACK/control processing. Reject a backend path that logs/discards it. |
| D-04: target filter/stock connector | Retarget only inside the owner and validate source/destination/full address width. No concurrent clients or stock connector that fixes all operations to one ECU. |
| D-05: cleanup and idle alive-check | Reconcile stale frames and service entity alive checks while idle and during requests; no competing reader. |
| D-06: discovery/routing/raw logs | Bind UDP/TCP to selection; validate header/length/entity/activation and preserve raw bytes even if library parsing consumes them. |

For each row record exact source method/hash, chosen adaptation and manual
observation. Prefer supported extension/composition; do not globally monkey-patch
libraries or copy a complete client/parser. If an adapter needs broad private
overrides or duplicate stack logic, stop that candidate's cutover and document
an upstream fix/alternative. Gallia comparison does not authorize asyncio or
an extra dependency. Keep current functionality until a replacement passes its
gate, then remove the superseded path; never ship two independently active owners.

## Ordered implementation and review units

Follow the detailed [development tasks](protocol-library-migration-tasks.md).
Dependencies are A1 → A2 → A3 → A4 → A5 → A6 → A7 → A8. Feasibility/source
inspection can inform earlier steps, but each backend must pass its own gate
before live cutover. Pin a dependency with its usable integration, not imports
alone; A6 finalizes the full closure. Use reviewable commits for:

1. A1: contracts/owner skeleton and cancellation/lifecycle boundaries.
2. A2: udsoncan bridge/services and exception/compatibility mapping.
3. A3: selected Scapy HSFZ adapter and retained-byte comparison.
4. A4: doipclient adapter or explicit evidence-backed candidate disposition.
5. A5: worker/UI routing, DEMO compatibility and removal of old loops.
6. A6–A8: dependency/legal/package closure, acceptance evidence and delivery.

An intermediate adapter is not wired to the GUI until its safeguards and worker
integration exist. Each commit must remain importable; every push needs the full
gate. Split into PRs only at working boundaries, with each later branch based on
current main after dependencies merge. Do not enable writes to validate adapters.

## Verification plan and completion criteria

Create `tasks/protocol-library-migration-verification.md` during implementation
to record revision, runtime, artifact identities, manual action, expected/actual
bytes/outcomes, evidence location/hash and limits for each case. Sanitized evidence
belongs under `docs/evidence/`; raw captures/large bundles stay local.

| Boundary | Required manual acceptance |
|----------|----------------------------|
| Owner/UDS | Queue time consumes deadline; session + request share one budget; NRC 78 stays bounded; final negative/wrong SID/echo are failures; per-ECU state is isolated. |
| Both adapters | ACK before/after diagnostic, short/coalesced headers/bodies, controls/NACK, malformed/oversized length, wrong endpoint, EOF, send failure, cancellation and late identical replies. Declare cases synthesized offline versus observed in the retained capture. |
| Policy/lifecycle | Block writes/clears/reset/routines/security before send via typed/raw/compatibility paths; cancellation before send sends zero bytes; post-send uncertainty prevents replay; close/reconnect drops stale callbacks and settles all workers. |
| Discovery | Selected source IP/interface used for UDP and TCP; validate full discovery identity, malformed replies and multiple responders. Preserve explicit candidates; do not silently choose the first car. Multiple-car UX remains a doc 21 product question. |
| DEMO/UI | Existing DEMO flows, loading/partial/error/unavailable states and disconnect responsiveness; no live history/coding activation, per-code clear route or real I/O on the GUI. |
| Owner F48 run | Owner-operated `--debug --read-only`: discovery, session, matching VIN, optional rejected reads remain partial. Compare to doc 23's hashed original and retain fresh logs. No adapter scanning, writes or network setup. |
| Runtime/packages | Fresh Python 3.13 install/import and source startup; launch bundles outside checkout on macOS arm64/Intel and Windows x64, with data/dynamic modules/notices and no capture driver/admin requirement. Record unavailable platforms as pending. |
| Static/CI | Full scripts/preflight.sh: Ruff lint, formatting and mypy separately green. Dependency changes also require the existing CI pip-audit result; do not claim it is part of the local three-command gate. |

Use manual local byte inspection/replay, without adding an automated suite,
`tests/` or a new CI testing path. The doc 23 capture proves HSFZ/VIN only;
it does not contain evidence for every injected failure or DoIP hardware case.
F48 validation cannot certify DoIP or broad fleet behavior. Implementation/
offline readiness, physical acceptance and platform packaging have separate
statuses; A remains incomplete while required acceptance is pending.

No automated suite or `tests/`; no vehicle writes, DHCP changes or unsolicited
scanner runs. Missing BMW feature contracts belong to Task B, not invented
constants inside an adapter. Do not disable existing supported behavior merely
to make the migration appear successful; explain any candidate limitation.

## Required handoff to Task B

Record the final connection/service API, exact module paths and dependency
versions, target-address/session model, how operation contracts register codecs,
failure taxonomy, cancellation/recovery contract and local evidence locations.
Update docs 25/26 and `SESSION-PROMPT.md` after merge. Do not mark B complete
or imply F/G/U/I coverage from A's F48 validation.

## Verification record

Planning-only verification, 2026-10-28: caller inventory and dependency/CI paths
inspected at the revision above. Full `scripts/preflight.sh` passed Ruff lint,
Ruff format (18 files) and mypy (18 source files), using Python 3.15.2. No new
dependencies were installed and no app code changed in this planning session.

Implementation, candidate feasibility observations, fresh Python 3.13 imports,
new offline/capture exercises, vehicle runs and platform packaging remain
pending. The existing wheel manifest and doc 23 are references, not observations
of the future migrated implementation.
