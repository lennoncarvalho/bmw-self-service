# Infrastructure readiness contract

Updated 2026-10-28. Existing implementation requires review, not rebuilding from
scratch. Earlier checked criteria and “39 tests” references were unsupported.
See [audit findings](docs/19-audit-and-readiness.md),
[protocol corrections](docs/20-protocol-evidence.md) and
[owner decisions](docs/21-product-decisions.md).

## Intended boundaries

Retain Python 3.13 target, Qt Widgets/QSS, one main window, QThread workers,
standard TCP/UDP and offline data assets. The initial cleanup changes guidance
and skills; it does not certify or alter runtime vehicle behavior.

## Acceptance criteria for the next implementation work

- Identify the actual wired link and route without confusing Wi-Fi, assigned IP
  or adapter naming with vehicle connectivity.
- Discover and validate the endpoint on the selected adapter; negotiate evidenced
  HSFZ/DoIP behavior rather than relying solely on a chassis selector.
- Serialize transport ownership; handle control/ACK/NACK/pending/fragmented/late
  frames with correlated responses and bounded overall deadlines.
- Establish valid vehicle identity before showing verified connected status.
  Optional read failures remain visible as unavailable/incomplete data.
- Keep every car I/O operation off the GUI thread, including keepalive and
  recovery. Cancellation/disconnect must actually settle outstanding work and
  prevent stale updates after reconnect.
- Use exact ECU/software and definition identity. Do not probe guessed writes,
  choose first-available coding variants or infer FA/SVT binary layouts as XML.
- Save a durable backup before coding/history writes; persist intended state
  and observed readback separately. Report success only after validation.
- DEMO must be explicit and isolated from real connection/recovery state.
- Preserve useful logs, actionable user errors and per-ECU failure results.
- Resolve dependencies/assets for fresh installs and launch outside the checkout.

## Current verification

The 2026-10-28 baseline passes all three full-app static gates. It does not
establish any of the above vehicle acceptance results. The local venv runs
Python 3.15.2 despite the 3.13 target. Physical coverage is limited to the
owner's F48/NBT; broader behavior needs source evidence and validation status.

Historical task files remain reference history. Plan new work from audit findings
and explicit owner decisions; do not interpret old checked boxes as a release gate.
