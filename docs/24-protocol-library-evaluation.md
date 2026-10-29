# Protocol library evaluation

Reviewed 2026-10-28 against released artifacts and primary project documentation.
Owner decision: GPL-compatible app distribution is acceptable. Reuse existing
protocol implementations where they satisfy the app's contract; do not rewrite
standard UDS/DoIP/HSFZ simply because the current app did so.

## Implementation disposition (2026-10-28)

The selected releases are now integrated. See the [verification record](../tasks/protocol-library-migration-verification.md)
for exact scope and each candidate gate. Scapy HSFZ codecs and doipclient
Parser/message types are reused with bounded ordinary TCP and control dispatch;
their high-level socket wrappers are not instantiated. udsoncan alone owns
standard UDS service validation/pending/timing. This refines the original wrapper
recommendation below; source findings there remain the reason for this boundary.
Fresh target Python 3.13 and local arm64 packaging were checked; physical and
other-platform acceptance remain pending. It does not recover BMW operations.

## Recommendation

| Layer | Preferred candidate | Decision |
|-------|---------------------|----------|
| Standard UDS services | `udsoncan` 1.26.1, MIT | Adopt as the planned UDS implementation. Its name does not restrict it to CAN; it accepts custom transport connections. |
| DoIP | `doipclient` 1.2.2, MIT | Preferred synchronous transport candidate. Reuse behind a project adapter, with the specific lifecycle gaps below resolved before switching live traffic. |
| HSFZ | Scapy 2.8.0 `HSFZSocket` / `UDS_HSFZSocket`, GPL-2.0-only | First integration candidate under the owner's accepted distribution direction. It fits synchronous QThread operation, but is not a complete diagnostic lifecycle. |
| Alternative HSFZ / DoIP / UDS stack | Gallia 2.2.0, Apache-2.0 | Credible alternative with explicit ACK/alive handling. Retain for comparison; adopting its asyncio transport needs an approved architecture revision, rather than silently mixing event loops into Qt. |

This is a dependency/architecture recommendation, not an implemented migration
or proof of production quality. Do not add all candidates to requirements.
The next implementation PR should establish a narrow adapter and choose one
owner for each protocol responsibility, avoiding two competing UDS dispatchers.

## Evidence checked

Downloaded the four current release wheels from PyPI without installing or
importing them; verified each against PyPI's SHA-256 and inspected packaged
source, metadata and licenses. Identities and selected source-file hashes are
in [the library manifest](evidence/protocol-library-inventory.json).
Local originals are under
`/Users/lennon/BMW-Tool/investigations/2026-10-28-protocol-libraries/`.

| Release | Uploaded | Python metadata | Required dependencies in base metadata |
|---------|----------|-----------------|---------------------------------------|
| udsoncan 1.26.1 | 2026-06-25 | >=3.7 | None; CAN/ISO-TP adapters are optional |
| doipclient 1.2.2 | 2026-08-23 | >=3.6 | None; its optional UDS connector imports udsoncan |
| Scapy 2.8.0 | 2026-10-02 | >=3.7,<4 | None; extras not needed for ordinary HSFZ TCP |
| Gallia 2.2.0 | 2026-10-13 | >=3.12,<3.16 | aiosqlite, argcomplete, platformdirs, pydantic, wcwidth; zstandard below Python 3.14 |

All four distribute `py3-none-any` wheels and their declared Python ranges
include the app's 3.13 target. This does not prove macOS/Windows/PyInstaller
compatibility; full dependency closure, imports, build size and packaged launch
must be checked during migration. Do not claim current local Python 3.15 is a
substitute for target Python 3.13 verification. Recent release dates establish
release activity, not a support guarantee or independent security certification.

## UDS: substantial reusable functionality

`udsoncan` builds/interprets standard services, validates responses and service
echoes, interprets negative responses, and handles NRC 78 with P2/P2* and a
monotonic response budget. `change_session` can use the ECU's advertised timing.
DTC records/status and standard ReadDataByIdentifier plumbing should not have
another parallel custom implementation in our app.

Its `BaseConnection` API permits HSFZ and DoIP adapters. Existing
`DoIPClientUDSConnector` connects doipclient to it. No CAN interface, python-can
or ISO-TP runtime is needed for our Ethernet paths. BMW DID selection and
`DidCodec` definitions still need exact variant evidence.

Adapter requirements from inspected `udsoncan/client.py`:

- `send_request` calls `empty_rxqueue` before sending. Our adapter must resolve
  a timed-out outstanding transaction before allowing another send; it must
  not discard partial frames or pending-response ownership as queue cleanup.
- The library's overall response timer starts **after** `conn.send`. Keep the
  app's outer monotonic budget covering lock queueing, transport ACK wait and
  send, and cap each receive by the remaining budget. Merely setting
  `request_timeout=30` does not reproduce the app's whole-operation deadline.
- Keep one serialized transaction/session owner, including TesterPresent;
  mutable client/session state must not be accessed by independent GUI workers.
- Retain negative/invalid/unexpected response exceptions and translate them
  to explicit unavailable/error outcomes. The FA task could still hide an
  exception by returning empty fields; changing libraries alone cannot fix it.

Sources: [project/release](https://pypi.org/project/udsoncan/1.26.1/),
[connection API](https://udsoncan.readthedocs.io/en/latest/udsoncan/connection.html),
[client configuration](https://udsoncan.readthedocs.io/en/latest/udsoncan/client.html),
[client source](https://udsoncan.readthedocs.io/en/latest/_modules/udsoncan/client.html).

## DoIP: reusable, with adapter obligations

The released client implements stream parsing, discovery/identification,
routing activation, diagnostic ACK/NACK and alive-check replies. It supports
source-IP binding and synchronous calls suitable for CarWorker. Defaults,
tester addresses and activation type still need source-supported BMW selection.

Specific release-source behavior to address before adoption:

- `auto_reconnect_tcp=True` permits reconnect and resend in `send_doip`.
  Leave it disabled. An uncertain mutation must never be automatically replayed.
- `read_doip` uses wall-clock time and blocking receives; `receive_diagnostic`
  resets its timer for diagnostic traffic from another ECU. Enforce the app's
  independent monotonic overall deadline without depending on these timers.
- `send_diagnostic_to_address` waits for transport ACK and logs/ignores other
  message types during that wait. Establish behavior for a diagnostic reply
  arriving before the ACK rather than assuming it will be retained.
- `receive_diagnostic` filters the configured ECU address. The stock connector
  uses that configured ECU; multi-ECU addressing requires explicit adapter
  design and serialization, not concurrent clients consuming the same socket.
- `empty_rxqueue` is currently a no-op. It does not solve stale responses;
  reconnect or reconcile outstanding traffic according to our contract.
- Alive checks are processed while receiving. Define connection idle servicing
  so the gateway can be answered while the GUI is quiet.

These are inspected implementation boundaries, not claims of observed vehicle
failures. Prefer a small wrapper or upstream correction where possible. If
required changes become a second full client, reconsider the backend rather
than wrapping an unbounded collection of patches.

Sources: [release](https://pypi.org/project/doipclient/1.2.2/),
[project and declared synchronous scope](https://github.com/jacobschaer/python-doipclient),
[connector](https://python-doipclient.readthedocs.io/en/latest/connectors.html).
Exact inspected methods are in `doipclient/client.py`: `Parser`, `read_doip`,
`send_doip`, `send_diagnostic_to_address`, `receive_diagnostic`, `_connect`.

## HSFZ: real implementations exist

Scapy includes typed HSFZ framing, control words, stream socket buffering and
UDS socket wrapping. This is more than a packet-field description. Its HSFZ
socket creates an ordinary TCP socket to port 6801; that path does not use
pcap/raw capture. Do not impose root/Npcap merely because Scapy supports other
packet-capture features.

The shipped `UDS_HSFZSocket.recv` returns UDS for a diagnostic frame and can
return the original packet for controls such as ACK. The application still
needs a control dispatcher. `send` catches errors, closes and returns zero;
the adapter must surface failure explicitly. Constructors do not expose our
selected local IPv4 binding. Full transaction correlation, pending/late replies,
deadlines, session keepalive and read-only enforcement are not supplied by
these socket wrappers. Do not invoke the bundled broad endpoint scanner as
an automatic replacement for source-derived ECU inventory.

Gallia provides an HSFZ connection with a background reader, exact header/body
reads, ACK/address/payload matching, incoming alive-check replies and transport
timeouts. It is a stronger lifecycle comparison candidate. Its mutex covers
write plus ACK, while the app still needs ownership of the complete diagnostic
request/reply. Source binding, length limits, reader shutdown propagation and
unexpected-frame handling also need evaluation. Its transports use asyncio;
the current app explicitly uses QThread without asyncio. A dedicated backend
design would need review before this becomes the primary runtime.

Sources: [Scapy HSFZ code](https://github.com/secdev/scapy/blob/master/scapy/contrib/automotive/bmw/hsfz.py),
[Scapy automotive documentation](https://scapy.readthedocs.io/en/stable/layers/automotive.html),
[Scapy release/license](https://pypi.org/project/scapy/2.8.0/),
[Gallia release/license](https://pypi.org/project/gallia/2.2.0/).
Gallia's exact inspected file is `gallia/transports/hsfz.py` in the recorded
release wheel, also available from its
[publishing commit](https://github.com/Fraunhofer-AISEC/gallia/blob/91a141908439034dee9142a52038637cd28b8792/src/gallia/transports/hsfz.py).

The owner accepts GPL-compatible distribution, so Scapy is not excluded by an
assumed closed-source requirement. Record the chosen app license and preserve
required third-party notices/source distribution materials before release.
MIT/Apache dependencies also require their applicable notices. No dependency
or app license was changed by this evaluation.

## What libraries will not recover

Transport/UDS reuse does not provide BMW ECU topology, variant selection,
correct mileage/voltage/FA/I-level mappings, history record codecs, live coding
data or signed-coding authorization. Those still come from the source-first
REA investigation. The retained session's `7F 22 31` remains a rejected request
when the same bytes are sent through a library. Switching to DoIP would not
address a car already answering correctly over HSFZ.

Other candidates were screened: python-uds 1.0.2's base metadata pulls CAN/LIN
dependencies and offers less direct benefit for this stack; no detailed quality
verdict is claimed. ECUmulator.py advertises HSFZ/DoIP REPL/emulation tools,
but is not established here as a preferable embeddable client. BMW-specific
Rust/TypeScript tools are possible research references, not Python drop-ins.
This is a bounded candidate evaluation, not a claim no other library exists.

## Migration acceptance and order

1. Introduce one narrow project connection API. Reuse udsoncan service codecs
   first; split raw transport framing from UDS transactions. Avoid layering its
   Client over today's blocking `send_uds` and creating two request lifecycles.
2. Evaluate Scapy HSFZ behind that API using the retained capture and manual
   offline byte inspection. Verify adapter behavior for ACKs/controls, fragmented
   input, pending/late replies, wrong endpoints, timeout/cancel, EOF, and source
   binding. Reject a migration that loses the safeguards already implemented.
3. Evaluate doipclient through the same API, keeping reconnect/resend disabled
   and resolving the source-observed boundaries above. Compare Gallia if either
   adapter requires extensive core changes. Pin only the selected releases.
4. Preserve raw transport logs, per-request IDs, read-only policy before send,
   per-ECU identity, monotonic deadlines and no uncertain write replay. Keep
   diagnostics on background threads. Require full static gates and packaging
   verification; no automated suite is authorized by this plan.
5. Validate the selected read-only backend on the owner's car, then expand
   evidence-backed variant coverage. Dependency migration and BMW-specific read
   recovery are separate acceptance items; both are needed.

No installed dependencies, runtime app code, car state or host configuration
changed. No candidate was imported/executed or physically validated here.
