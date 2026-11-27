# Implementation tasks

Work in priority order. Update these steps in place when the implementation
changes; remove completed detail instead of appending session or PR reports.
Current source contracts and reproduction routes are in [docs.md](docs.md).

## Easy Coding write acceptance

The implementation milestone is closed with the current source-backed coverage.
Known source limitations remain in `docs.md`; only physical write/restore
acceptance remains in this milestone.

- [ ] Verify a live supported coding change and explicit restore after any required
  cycle. From Backups, run **Verify coding after vehicle cycle** on each completed
  operation and retain the session log and comparison. Response-confirmed
  outcomes remain separate from observed verification.

## History and integrated acceptance

- [ ] During the next intended physical ENTRYNAV append, verify KL15 at
  execution and compare the checked ADD and activation responses with the date
  and items shown in iDrive. Preparation has reached review on KL15.
  Replacement requires an independently intended operation.
- [ ] Confirm live reconnect after a naturally interrupted read and Clear All
  results during an intended fault clear. Retain actual identities and outcomes.
- [ ] During an intended car session, compare the latest Overview MIL read with
  the cluster lamp after startup. Retain the lamp observation and command reply.

## Later implementation choices

- [ ] After Service Functions implementation is authorized, compile an allowlist
  from the [catalog and PRG contracts](docs.md#service-functions-source-contracts).
  Verify identity/rule inputs, job phases and result decoding. Cover additional
  ECU variants where the same behavior has source evidence.
- [ ] Exercise individual lighting, timed interior-mirror dimming and audio tone
  through the existing owner and DEMO. Check incompatible equipment, rejected
  commands, timeouts, disconnects, stop/release and post-state.
- [ ] Compose the walk-around from verified lamp outputs. Check safe concurrent
  groups, access to each phase, duration, early exit and release when a stage
  fails partway. Require confirmed fitment and control return before live use.
- [ ] Add the display/radio, HVAC, washer, switch, parking sensor, horn and
  brake-fluid checks from the source guide. Admit wiper/mirror, seat, window and
  powered tailgate movement only with verified bounds on lost communication.
  Recover guided learning and initialization procedures separately.
- [ ] Recover the TPMS measurement and equipment reads for supported variants.
  Check corner assignment, stale or missing sensors and incompatible equipment.
  Establish the F48 retrofit prerequisites from the exact hardware and vehicle
  order before proposing parts or coding.
- [ ] Decode stored parked-current durations and variant-specific wake-up
  history. Verify that the feature uses read-only requests and labels historical
  data and unavailable values explicitly.
- [ ] Recover like-for-like 12 V battery registration contracts, including the
  configured type/capacity, required inputs, power and ignition conditions, and
  before/after history. Verify the exact request, rejected or uncertain writes,
  unchanged or ambiguous history, and no automatic replay in DEMO.
- [ ] Show semantic feature/option names in coding backup comparisons alongside
  original/intended bytes, using exact saved-definition matching. Current
  comparisons retain bytes and do not explain each changed setting.
- [ ] Recover full-width DoIP ECU inventory and feature-address mappings, then
  enable the supported diagnostic/CBS/coding/history paths. Existing discovery
  and routing do not establish feature-level support or support for newer releases.
- [ ] Add source-backed DEMO profiles and a DoIP simulation. The current DEMO
  covers one HSFZ profile.
- [ ] Implement Advanced Coding and separately validate deferred coding targets
  when that scope is selected. Existing Easy Coding remains complete for this milestone.
- [ ] Validate Windows and Intel Mac operation, including native library builds.
- [ ] Prepare packaged releases: bundle/runtime asset checks, signing and the
  release/distribution requirements in `THIRD_PARTY_NOTICES.md`.
