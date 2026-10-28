# First retained read-only vehicle session

Observed locally, 2026-10-28. This report establishes a limited connection
baseline and documents failed reads; it does not establish fleet support.
The next work is [the REA recovery plan](../tasks/rea-protocol-recovery.md).

## Capture identity and scope

- File: `session-20261028T210910.031486Z-37770.log`, 90,404 bytes, 688 lines.
- SHA-256: `ecd7d39b5dc1d889354819ded4e410fb21ff729df743fc7d48b5123dc5ae24fa`.
- Original: `/Users/lennon/BMW-Tool/logs/`; identical local preservation copy:
  `/Users/lennon/BMW-Tool/investigations/2026-10-28-read-session/`.
- App revision: `6bdb8f3232d3035de37b10ba4c77608608ef4c30`; its app sources
  match merged main `c866f83` at investigation start.
- macOS arm64, Python 3.15.2, PySide6/Qt 6.12.0; `debug=True`, `read_only=True`.
- Selected F-series/HSFZ, USB Ethernet interface `en15`, link-local addressing.
- Two TCP connections; 28 logged diagnostic request/reply pairs, plus separate
  keepalive traffic. Vehicle identity is omitted from this shared report.

The raw file remains local because it contains VIN, MAC and host information.
Line numbers below refer to the original complete capture, not an excerpt.

## What worked

First connection: lines 35–64, 21:09:20 UTC. Second: lines 438–467,
21:10:59 UTC. UDP discovery, TCP port 6801, extended diagnostic session and
VIN read completed on both attempts. `10 03` returned `50 03 00 32 01 F4`;
`22 F1 90` returned `62 F1 90` and the same 17 VIN bytes as discovery.

HSFZ control `0002` ACK frames were consumed separately from control `0001`
diagnostic replies, including fragmented header/body delivery. There is no
evidence of the earlier ACK-as-UDS problem in these requests. This capture
does not establish every framing, concurrency or DoIP path is correct.

All 28 logged diagnostic requests have corresponding replies. Optional reads
finished in about 66 ms and 47 ms respectively; their failures were negative
responses, not operation timeouts. Repeated `RX poll/deadline` entries are idle
keepalive polls, not evidence that those data reads timed out.

## Why data was missing

The same results occurred on both connections:

| Intended data | Address / request | Observed response | Consequence |
|---------------|-------------------|-------------------|-------------|
| I-level | `10 / 22 F1 8A` | `62 F1 8A 00 00 09` | App decodes binary `00 00 09` as ASCII and records a tab as successful I-level. This does not establish what F18A actually means. |
| Vehicle order / FA | `10 / 22 F1 00`, then `22 FC 00` | Both `7F 22 31` | Both rejected, but `_read_fa` returns an empty dictionary of fields and the worker records success. |
| Mileage | `60 / 1A 00`, then `10 / 22 F4 06` | `7F 1A 11`, then `7F 22 31` | Legacy service rejected; fallback DID rejected. No mileage data was received. Address 60's actual ECU identity is not established by the code's KOMBI label. |
| Battery voltage | `12 / 22 F4 0C`, then same at `10` | Both `7F 22 31` | Neither request returned voltage data. No valid decoder/scaling was exercised. |
| ECU topology | `10 / 22 F0 00` | `7F 22 31` | No ECU inventory; subsequent DTC scans fall back to gateway only. |

`7F <SID> 31` is requestOutOfRange; `7F 1A 11` is serviceNotSupported.
These reject the specific request in this endpoint/session/context. They do not
prove the car cannot provide the information through another supported path,
nor identify the correct endpoint, job, DID or prerequisite session.

First-attempt detail: lines 70–188. Second-attempt detail: lines 473–591.
Owning code: `ui/main_window.py::_build_post_connect_tasks`. Its hardcoded
F18A/F100/FC00/F406/F40C/F000 mappings and codecs were already unresolved in
[doc 20](20-protocol-evidence.md). The log's “2/5 succeeded” is misleading:
neither successful task produced a meaningful vehicle-information value.

Even a future positive F000 response would not establish a complete inventory:
`ui/vehicle_page.py::_parse_svt_response` searches ASCII names and does not
recover diagnostic addresses. Its parser also needs replacement from evidence.

## DTC requests succeeded, but the scan was incomplete

There were four scans, two per connection (lines 213–239, 293–317,
600–626, 639–663). Every scan logged `ecus=1 coverage_known=False` and
addressed only the gateway at `10`:

```text
request:  19 02 08
response: 59 02 4F
```

This is a positive response with availability mask `4F` and no DTC records for
the requested confirmed-status mask `08`. It is not an all-ECU clean bill of
health; it establishes no matching records at that endpoint at that time.
The code correctly records `complete=False`. Other ECUs were not scanned
because the topology read failed. Pending/current/history coverage and MIL
are separate requirements; this confirmed-only scan does not supply them.

Owning flow: `MainWindow._on_post_connect_finished` →
`DiagnosticsPage._read_dtcs` gateway fallback → `DtcReadWorker._read_dtcs`.
Recovering a real ECU inventory is the first dependency for complete diagnosis.

## History, coding and disconnects

History/coding navigation occurred, but the log explicitly records their live
readers disabled (lines 65–66, 211–215, 468–469, 598–601). Those pages did
not attempt vehicle reads. This follows the existing guard, not a newly
observed rejection by the car. Their source-backed read contracts remain work.

No mutating diagnostic SID appears among the 28 logged diagnostic requests.
This is evidence about the captured traffic, not a universal safety claim.
No vehicle traffic was generated during this investigation.

The first keepalive EOF appears immediately after the UI logs
“Disconnecting from vehicle” at 21:10:34 (lines 416–431). Local shutdown can
cause this receive result; the wording “closed by vehicle” does not establish
an unsolicited vehicle disconnect. The second disconnect is also initiated
through the UI (lines 683–686). No preceding data-read timeout or lost-link
event explains the missing data.

## Disposition

Connection/VIN: **observed working on this setup**. Mileage/voltage/FA/topology:
**requests rejected**. I-level: **semantically invalid decode**. DTCs:
**gateway confirmed-only read succeeded, vehicle coverage incomplete**.
History/coding: **disabled pending source evidence**.

Do not tune timeouts, change cable configuration or substitute new guessed DIDs
to address these results. First trace the reference apps' variant selection,
request construction and response decoders. Existing log detail is sufficient
to diagnose these failures; it cannot recover protocol paths never implemented.
