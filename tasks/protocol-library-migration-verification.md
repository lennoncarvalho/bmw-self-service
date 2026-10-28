# Task A implementation verification

Current status: code implementation and local review complete in
[PR #12](https://github.com/lennoncarvalho/bmw-self-service/pull/12).
The current library integration record below supersedes the retained A1-only
entry. Fresh vehicle, remaining-platform and release acceptance are still pending.

2026-10-28; implementation branch `codex/task-a-protocol-owner`, based on
main `4898b0a8586aa1e41236775356895c6375096a2b` with planning commit carried
forward. Owner authorization to proceed supersedes the plan's wait for a
separate planning merge. This first implementation slice is the A1 queue/
context foundation and coherent worker result-signal migration. It does not
complete A1 or Task A, and is not wired to live connections.

## Observed locally

One-off offline exercises (no persisted automated suite) using Python 3.15.2,
QCoreApplication and ProtocolWorker/QThread established:

- An expired queued context completes as timeout without invoking its callback.
- Pre-cancelled work completes as cancelled without invoking its callback.
- A valid queued operation returns its immutable byte result.
- Stop settles the queue and invokes resource cleanup on the executor thread.
- Submission after close returns a closed outcome without invoking its callback.
- A callback marking mutation/send then raising TimeoutError completes uncertain;
  queued work is closed, the owner exits and the callback is never replayed.

The callbacks contain no sockets or vehicle requests. These observations verify
queue/lifecycle boundaries only, not adapter deadlines, framing or wire policy.

Full `scripts/preflight.sh` passed Ruff lint, Ruff formatting and mypy over
`app/`, `ui/` and `main.py` (21 source files). No dependency changes or physical
vehicle requests were made. Python 3.13, visual DEMO and platform packaging
acceptance remain pending.

## Remaining implementation

A1 still needs facade integration, final discovery/config validation and
per-ECU session ownership. A2–A4 must implement and verify the service bridge
and selected transport adapters before GUI cutover. A5 still needs connection/
keepalive migration, cancellation propagation and asynchronous disconnect;
this slice only migrates result delivery coherently. A6–A8 runtime/package,
vehicle acceptance and final Task B API handoff remain open. No library or
vehicle support claim follows from the queue foundation.

# Library integration and code review — 2026-10-28

Implementation base: `18a8b34` (merged PR #11). Branch:
`codex/task-a-library-integration`. The earlier foundation-only scope above is
historical. **Code implementation and local review are complete**; the fresh
owner-operated vehicle run, Windows/Intel packaging and release licensing remain
acceptance items, not claims established by this PR.

## Final owning boundaries / Task B handoff

- `app/protocol/facade.py`: DiagnosticConnection, HSFZConnection/DoIPConnection;
  `submit_operation`, worker-only `run_operation`, classified `request`, temporary
  raw `send_uds`, caller cancellation, `register_ecu`, asynchronous `disconnect`.
- `contracts.py`: validated ConnectionConfig, EcuIdentity, session snapshots,
  one submission-time OperationContext, immutable OperationOutcome/FailureKind.
- `owner.py` + `app/worker.py: ProtocolWorker`: one executor for live TCP, all
  clients, idle controls and per-ECU keepalive. Shutdown retains owners including
  connection-setup races and settles active/queued operations.
- `stream.py`: ordinary source-bound TCP, bounded nonblocking send/receive,
  complete envelope validation and persistent partial buffers. No capture driver.
- `discovery.py`: both actual transports on selected IPv4/broadcast; validates
  identity, rejects multiple distinct vehicles and cross-checks diagnostic VIN.
  When the same entity advertises both transports, prefer observed HSFZ.
- `hsfz.py`: Scapy 2.8.0 HSFZ packet definitions/serialization, explicit control
  length handling and addressed diagnostic dispatch.
- `doip.py`: doipclient 1.2.2 Parser/message types/serialization; high-level
  DoIPClient socket/ACK/receive loops are not instantiated. The adapter owns
  bounded routing/ACK/control dispatch, full logical addresses and early replies.
- `udsoncan_connection.py` + `app/uds.py`: udsoncan 1.26.1 owns standard service
  encoding, SID/echo/NRC/pending/P2/P2* and DTC decoding. Final negative replies
  remain classified failures; only compatibility send_uds returns their raw bytes.
- `UdsServices.register_codecs(CodecRegistration(...))`: owner-applied immutable
  DID configuration keyed by exact EcuIdentity plus definition ID/full SHA-256.
  Refine identity using register_ecu first. Unknown variant/software cannot
  register BMW codecs. Conflicts/duplicate DIDs are rejected. Built-in VIN is
  exactly 17 ASCII characters; unknown DID compatibility remains opaque bytes.

Task B should submit a complete session/read sequence with one context. Its
operation callback receives `(UdsServices, OperationContext)` on the owner and
must not access widgets. Read-only checks apply to actual encoded bytes at each
adapter send, including generic/compatibility/service requests. No independent
transport/client or pending-response loop belongs in Task B.

## Candidate gate dispositions

| Gate | Final disposition |
|------|-------------------|
| U-01 | empty_rxqueue rejects unfinished requests; adapter.prepare reconciles available controls/partial frames and rejects stale diagnostics. Nothing is blindly drained or reset. |
| U-02 | Original deadline includes queue, send/ACK, receive and pending; library P2/P2* waits are capped by it. |
| U-03 | Explicit opaque BaseService extensions preserve existing 0x01/0x1A compatibility without BMW decoders. Other unsupported service shapes fail before send; inactive security/coding/history consumers remain guarded. |
| H-01 | Source-bound ordinary TCP plus Scapy HSFZ codec reuse; HSFZSocket constructors are not used, so no unbound socket or raw-capture requirement. |
| H-02 | Shared bounded envelope/fragment buffer and Scapy type parsing; ACK/control traffic is separate from udsoncan. |
| H-03 | UDS_HSFZSocket.send is not used; BoundedStream checks zero/failed sends and treats attempted mutations conservatively. |
| H-04 | Diagnostics use Scapy serialization; controls specify type-specific length. Retained session/VIN request frames match exactly. |
| D-01 | No high-level DoIPClient instance/reconnect/resend path exists. |
| D-02 | BoundedStream uses monotonic absolute context; unrelated frames cannot reset it. |
| D-03 | Addressed diagnostic replies arriving before ACK are retained with a bound; manual reversed-order socket exercise passed. |
| D-04 | Full-width target identity is selected per owner operation; independent per-ECU clients share exactly one stream. |
| D-05 | Idle controls run on the owner; stale/early diagnostics block new sends or close the stream. |
| D-06 | Source-bound discovery/TCP, bounded header/body and checked activation identity/status; raw fragments/frames are logged. |

This is a documented refinement of the initial high-level socket-wrapper
recommendation: reuse released codecs/parser and implement only the application's
required bounded socket/policy/control boundary. The old two full transaction
loops and app-owned standard UDS framing/NRC parser have been removed. Gallia,
CAN/ISO-TP and capture extras were not added. The exact source methods/wheel
hashes remain in docs/evidence/protocol-library-inventory.json.

## Observed locally on the integrated implementation

- Fresh isolated Python **3.13.18** installed all declared dependencies; source
  imports and MainWindow construction succeeded. Python 3.13 mypy also passed.
- One-off socket exercises through both full facades passed session/VIN,
  fragmented headers/bodies, separate HSFZ ACK, HSFZ pending then final reply,
  DoIP diagnostic-before-ACK, full-width DoIP target 0x1234, final negative
  response without disconnect, policy-blocked clear followed by usable read,
  wrong-DID echo rejection and owner closure.
- Additional offline boundary inspection passed oversized HSFZ length, invalid
  DoIP inverse version, EOF, retained partial header across a short timeout,
  five blocked mutation/reset/routine/security service classes per adapter,
  cancellation before send with zero bytes and stale response rejection before
  a new send.
- Both adapters were exercised under repeated pending responses, unrelated ECU
  frames and post-send cancellation with a 120 ms operation budget. Each settled
  within 500 ms, closed queued work and transmitted exactly one request without
  replay. These are synthetic offline timings, not vehicle measurements.
- Doc 23's complete retained log SHA-256 was checked. Scapy serialization of
  `10 03` and `22 F1 90` matches the original captured HSFZ request frames.
  This is a byte comparison, not a new physical vehicle session.
- DEMO connected/populated its vehicle page in a Qt event loop outside checkout;
  its screenshot was visually inspected. DEMO values remain simulation data.
- Full scripts/preflight.sh: Ruff lint, Ruff formatting and mypy passed across
  all 28 source files. Fresh Python 3.13 pip-audit: no known vulnerabilities.
- macOS arm64 PyInstaller 6.22.3 onedir `.app` built (about 200 MiB), contains
  resources and dependency notices. `--help` exits zero and read-only startup
  outside checkout remains running without import/resource exceptions. No
  vehicle is connected during this launch check. It is an ad-hoc local build,
  not a signed/notarized distribution or a hardware validation.

One-off investigation scripts/logs and builds live under `/tmp/bmw-task-a-*`;
no automated suite, test directory or CI test path was added. Large binaries
and raw vehicle logs are not committed. The retained capture's original identity
and location remain in doc 23. Sanitized integration identity is recorded in
`docs/evidence/task-a-library-integration.json`.

## Review findings resolved before PR

Reviewed ownership/import graph and all old send/keepalive/cancel callers.
Resolved caller-context leakage across threads, native result/lifecycle signal
separation, unowned/partial receive cleanup before send, timeout/cancel stream
invalidation, main-window observation of clean owner termination, late-result
filtering, diagnostic fallback to the actual discovered gateway address,
shutdown during connection setup, cancellation of ECU prompt waits,
opaque optional-field failures and resource paths independent of working directory.
SQLite changes only resolve/escape the read-only asset path; queries/schema and
worker connection ownership are unchanged. Live history/coding guards remain.

Protocol-layer acceptance is not vehicle mutation verification. Clear responses
are described as requests accepted followed by reread; Task B still owns complete
all-ECU results/readback semantics. No unsupported history/coding operation was
made available. Legacy single-code clear UI/send path was removed per D-16.

## Behavior refinements and remaining acceptance

- New setup uses a 30-second overall discovery/connect/activation/identity budget,
  with discovery/connect/activation capped at 5 seconds each. Failed discovery
  gives cable/ignition/IPv4 guidance; it does not automatically invoke the old
  unvalidated privileged DHCP fallback. The helper remains for separate network
  setup work; its ownership/elevation UX is still pending in doc 21.
- Session keepalive uses standard unsuppressed TesterPresent on each active ECU
  with a checked reply. Incoming transport alive controls are dispatched; the
  old unverified periodic tester-initiated HSFZ 0x12 sender is retired. This
  profile change needs the fresh read-only F48 acceptance run.
- Unknown optional fields remain unavailable/partial. This migration does not
  validate the old FA/topology/mileage/voltage mappings. Empty FA and nonprintable
  I-level no longer become successful fields.
- Windows x64, Intel macOS and DoIP hardware were not available. Their package/
  hardware acceptance remains pending; arm64 HSFZ evidence cannot certify them.
- Owner-operated fresh F48 read-only acceptance remains pending. No car writes,
  actual network reconfiguration, scanner runs or DHCP/elevation actions occurred.
- GPL-compatible direction is accepted; exact application license and complete
  release source materials still need owner/release disposition before distribution.

Delivery: PR #12 is open on `codex/task-a-library-integration`; local/full-target
gates and GitHub quality/CodeQL checks passed. Subsequent local review corrected
gateway fallback addressing, distinct request trace IDs and closed-owner retry
behavior. The optional Robin review of the opening revision was still processing
at this handoff update; it is separate from the completed local code review.
