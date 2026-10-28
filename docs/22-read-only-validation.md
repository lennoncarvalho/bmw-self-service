# Read-only vehicle validation and debug capture

Updated 2026-10-28. Source implementation and static checks are not proof of a
successful connection or of support for every ECU. PR #8 is merged; subsequent
code changes use a separate branch and PR.

## Launch from this Mac's source checkout

From the repository root, using the branch containing this change:

```bash
.venv/bin/python3 main.py --debug --read-only
```

The window title includes READ ONLY. Select F-series for the current F48 target
and the actual wired ENET adapter, then connect. Adapter labels remain heuristic;
use the real OS interface identity, not an assumed enX index.

`--read-only` blocks data-changing UDS requests at both real transports before
socket transmission. The existing read services 01/19/1A/22 and default/extended
diagnostic sessions (10 01/03) and TesterPresent (3E 00/80) are allowed. Programming
sessions, security access, routine requests, writes, resets and fault clears are
blocked. DoIP also checks diagnostic payloads at the final TCP sender; only
routing activation (0005) and alive responses (0008) are exempt transport control
messages there. UDP discovery requests identify the gateway without changing
vehicle records. HSFZ keepalive sends fixed alive-check / 3E 80 messages.
This boundary does not certify any BMW-specific DID or decoder. Normal
launch without this flag does not enforce the same transport allowlist.

No automatic DHCP/network changes run in this validation mode. A discovery
failure is reported with existing interface settings preserved. Diagnostic
sessions/keepalive still communicate with the car; read-only means no vehicle
record/coding changes, not zero traffic.

## Page expectations

| Page | What this run can establish |
|------|----------------------------|
| Vehicle | Correlated VIN plus available optional reads; failures remain explicit. Existing BMW-specific data mappings are still under review. Compare displayed values with known vehicle facts. |
| Diagnostics | Confirmed DTC records from addressed ECUs. Negative, malformed, skipped and failed reads produce incomplete coverage, not a clean-car claim. Gateway-only fallback is incomplete coverage. |
| MIL and snapshots | Unavailable pending a verified emissions endpoint and ECU-specific snapshot codecs. The old guessed gateway MIL and timestamp/mileage decoding are no longer used. |
| History | Page opens with an explicit unavailable reason. No live read is attempted: the old 31 01 A0 81 request may start an add routine. DEMO history remains separate. |
| Coding Easy / Advanced | Both tabs open with an unavailable reason. No real coding values, mock fallback, guessed variant selection or generic coding probes are presented as live support. Live writes/restore remain disabled until exact definitions and readback exist. |

A successful diagnostic response or zero confirmed codes cannot establish overall
vehicle health. Exact ECU aliases may be missing from the description database;
show the raw code/status with an unavailable description instead of another
ECU's text. Service history/coding reads still require research, not a car-side
routine probe under the label “read.”

## Logs to retain

Unless --no-log is selected, the console prints a unique path on startup:

```text
~/BMW-Tool/logs/session-<UTC timestamp>-<PID>.log
```

Keep that session file and any matching `.log.1` through `.log.5` segments. Each
segment is capped at 10 MiB; a new launch gets its own name instead of overwriting
an older run. The previous uds.log files are left untouched. Do not use --no-log
for the vehicle session. Logs stay local and can contain the full VIN/MAC and
raw vehicle data; they are not published by this workflow.

With --debug the capture includes:

- UTC milliseconds, elapsed process time, thread, source revision, Python/Qt,
  working directory, adapter IPv4/netmask/broadcast and selected interface.
- Discovery TX/RX bytes and sender, TCP local/peer endpoints and a connection ID.
- Request IDs, ECU/SID/payload, queue budget, elapsed time and outstanding replies.
- Raw HSFZ/DoIP frames including ACKs, control messages and unrelated responses;
  fragmented bytes, retained buffer lengths and timeout/failure tracebacks.
- Keepalive traffic, worker durations, parsed post-connect results, page
  navigation, unsupported operations, Qt warnings and uncaught Python exceptions.

After the run, preserve the session and describe the last successful page/read,
visible error and approximate time. This permits a diagnosis without treating
an ACK as application success or confusing a previous launch with this one.

## Verification boundary

Full Ruff lint/format and mypy are required before publishing. No automated
behavioral suite is added, per owner policy. App startup, log creation and a
visible READ ONLY title were observed on this Mac. Native UI automation could
inspect the window but did not activate its gear menu reliably; no complete
DEMO page walk or vehicle validation is claimed. See the implementation record
in tasks/read-only-car-capture.md and remaining issues in doc 19.
