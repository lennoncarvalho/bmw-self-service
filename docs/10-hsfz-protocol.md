# HSFZ transport contract and open evidence

Reviewed 2026-10-28. Replaces the previous “complete/production” example.
Read [protocol evidence](20-protocol-evidence.md) and
[readiness findings](19-audit-and-readiness.md) alongside this contract.

## Corroborated framing

[Scapy's HSFZ implementation](https://github.com/secdev/scapy/blob/master/scapy/contrib/automotive/bmw/hsfz.py)
defines TCP 6801, UDP 6811 and a six-byte base header:

| Offset | Size | Meaning |
|--------|------|---------|
| 0 | 4 | Big-endian body length |
| 4 | 2 | Big-endian control word |
| 6 | length | Type-specific body |

Diagnostic (`0x0001`) and transfer-ACK (`0x0002`) bodies include one-byte
source and target addresses. A diagnostic payload of N bytes has length N+2,
with total frame size N+8. Target identifies the addressed ECU; do not invent
an inner routing header to send every request to the gateway.

Not every control frame contains source/target. Scapy distinguishes two-byte
alive-check bodies from longer identification strings; `0x0040` carries
expected/received tester addresses. Do not unconditionally consume eight bytes.

The existing discovery request candidate is `00 00 00 00 00 11`. Validate
returned header, body, sender and identity. Scope UDP and TCP to the selected
adapter and derive broadcast/route from its configuration.

## Historical connection evidence

PR #8 reports an F48 transfer ACK preceding a UDS response, then a session
response consumed by the next VIN request. The local log was empty during this
audit, so the original frame sequence could not be replayed. This is a
historical report, not a fresh end-to-end connection validation.

ACK handling is necessary; ACK does not prove ECU completion. Consume control
frames until a correlated application response or bounded failure occurs.

## Required lifecycle

- One owner serializes all socket I/O, including keepalive. Parse the base
  header, validate lengths/types, then read the complete body.
- Preserve fragmented bytes, or invalidate the connection after losing framing.
  A short drain must not discard a partial header or body.
- Match ECU addresses, UDS SID and DID/subfunction. A lock cannot match a late
  response to the correct request.
- Handle `7F <requested SID> 78` as pending. Apply a monotonic deadline across
  queueing, send, header/body and later frames; do not reset it for each fragment.
- Resolve late responses after timeout/cancel before reuse. Prevent stale workers
  from acting on replacement connections. Hiding a spinner is not cancellation.

The [PR review follow-up](../tasks/pr-8-review-followup.md) implements the
six-byte parser, persistent fragments, request matching, pending handling and
one operation deadline in source. Receive timeouts retain outstanding-request
ownership; its completion must be consumed before the next diagnostic send.
There is no automatic request replay. A never-completing response requires
reconnect before further diagnostics. Transport errors close the stream.
Static gates passed; real gateway behavior is not yet certified.

## Keepalive uncertainty

The old document asserted a tester-initiated `0x0012` every two seconds and a
guaranteed ACK. Neither the retained PR excerpt nor Scapy's framing code
establishes this behavior. Determine initiation, response and timing from a full
trace or primary connection implementation first.

Transport alive-check and UDS TesterPresent are separate. TesterPresent must
maintain relevant ECU sessions; sending only to the gateway is insufficient
proof. Skipping a timer cycle is not universally harmless.

The old interpretation of `7F 10 21` was incorrect: it identifies rejected SID
`0x10` with NRC `0x21` (busyRepeatRequest), not a TesterPresent response. See
[UDS response rules](20-protocol-evidence.md).
