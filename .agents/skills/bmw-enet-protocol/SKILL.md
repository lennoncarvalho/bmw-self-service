---
name: bmw-enet-protocol
description: Review or implement BMW ENET discovery, HSFZ, DoIP and UDS request lifecycles; diagnose connection and response-stream failures.
---

# BMW ENET protocol work

Read `docs/20-protocol-evidence.md`, `docs/10-hsfz-protocol.md` and the
connection findings in `docs/19-audit-and-readiness.md`. For undocumented BMW
payloads, use source analysis or REA; a plausible DID is not a mapping.

- Diagnose stages separately: physical link, interface/address/route, discovery,
  TCP, DoIP routing activation where applicable, UDS identity, optional reads.
  An interface name or assigned IP does not establish an Ethernet link.
- Scope UDP and TCP to the selected adapter. Validate discovery responses;
  preserve gateway identity and distinguish multiple responding vehicles.
  A series name is a hint, not conclusive transport evidence.
- HSFZ has a six-byte base header, with type-specific body fields. Read the
  entire declared body before dispatch; diagnostic frames include source/target.
  Consume transport ACKs separately from diagnostic replies. Preserve fragmented
  stream data; do not drop partial frames during a short heartbeat read.
- DoIP uses an eight-byte header; validate version/inverse, lengths and addresses.
  Validate routing activation before diagnostics. Handle ACK, NACK, alive-check
  and diagnostic frames through one socket owner; do not assume two receives.
- Serialize complete transactions, including keepalive traffic. Correlate ECU,
  SID, DID/subfunction and negative-response SID. After timeout, account for a
  late response before sending another request. A lock alone cannot do this.
- Handle NRC `0x78` as pending within a bounded transaction; use session P2/P2*
  timing where supported and a monotonic overall deadline including queueing.
  Repeated socket reads must not reset that deadline. Keepalive targets the
  relevant active ECU sessions; it must not perform blocking work on the GUI.
- Keep manufacturer-specific FA/SVT, mileage, voltage, coding and history
  mappings versioned by gateway/ECU/software. Never infer XML or byte scaling
  from display labels. Missing/unsupported data stays explicitly unavailable.
- Do not auto-replay writes, probe security keys, change the host network or
  start privileged services as part of this review. Record what evidence would
  resolve the next uncertainty, and use read-only captures first.

Report capture/artifact identity, exact bytes and interpretation separately.
Mask vehicle identifiers in shared reports without losing local traceability.
