# D-56 connection dashboard implementation

Scope: enrich the existing Task B branch/PR13 with a settled first-page overview,
manual refresh, explicit source/coverage states and an independently reported MIL.

1. Recover any remaining exact-variant MIL decoder before enabling its read.
2. Extend the existing read batch, preserving exact identity and optional failures.
3. Render VIN/connection metadata, software levels, supply voltage, ECU coverage
   and expandable ECU details. Unknown model/build/mileage stay unavailable.
4. Add refresh using the existing background worker/session checks and mutation
   guard; invalidate old observations on disconnect, mutation and stale age.
5. Independently review, exercise offline/offscreen flows, run full preflight.

No new user decision is pending. No vehicle operations or physical validation
are implied by static source recovery. Sensor metadata alone does not enable a
sensor. No history or coding work is included in this dashboard slice.

## Implemented / verification

- `app/vehicle.py`: inventory identity feeds a direct `22 4A69` MIL read only
  for exactly identified HSFZ MEVD172, MEVD172Y, MEVD1725 at address12. Accept
  exactly `62 4A69 00/01`; all other responses remain unavailable. No probing,
  security access, dynamic definition, actuation or DTC-bit substitution.
- `ui/vehicle_page.py`: settled connection/voltage/software/coverage summary,
  inline ECU details, labelled tri-state MIL, observation age and refresh.
  Unknown model/build/odometer remain explicit. No widget performs car I/O.
- `ui/main_window.py`: refresh reuses the owned CarWorker and session guards,
  blocks during mutations, refreshes after clearing, resets on disconnect and
  invalidates observations on connection loss. Refresh does not restart other
  pages or their operations.
- `assets/theme.qss`: centralized red/on, green/off and grey/unknown indicator.

Timing: existing per-task30s scopes remain; inventory, MIL, software and voltage
make a maximum120s of bounded task budgets, including each task's queueing.
The MIL timestamp starts at its actual completed read, not later publication.
After60s its indicator becomes grey and requests manual refresh; wall-clock
changes cannot keep it green. No periodic vehicle polling is added.

Offline one-off verification (no suite created): all3 exact identities and
request ordering, unknown identity/DoIP zero MIL requests, empty/truncated/wrong
DID/extra/sentinel replies rejected, bool0/1 decoded, stale-before-publication
invalidated. Offscreen widget/shell checks cover on/off/unknown colors with text,
inline details, coverage, DEMO, write lockout, post-operation refresh and reset.
Rendered900x650 overview was inspected. Full preflight passes33 modules.

Physical-car and broader-engine acceptance remain open. Source recovery does
not establish that the owner's F48 has one of these exact identities. Additional
sensor/configuration decoders remain separate recovery work.

Independent review found a late-result race during the lost-connection modal:
a settled queued result could re-enable/color an already dead connection. The
publication boundary now checks active connection identity, owner liveness and
closing state, and rechecks after modal delivery. A synthetic dead-owner result
was exercised and stays grey with refresh disabled. Diagnostics now mirrors the
same MIL observation/age invalidation; reading faults cannot reset or invent it.
