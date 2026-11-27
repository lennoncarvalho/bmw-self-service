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

## Service Functions

The initial page covers washer fluid, brake fluid, radio reception, climate
temperatures, the last IBS wake-up reason, windshield wiper service position
and timed interior mirror darkening. Availability depends on the exact vehicle
and ECU contracts. During intended use, compare the five readings, reported
mirror dimming and actual wiper positions with vehicle observations.

### Future functions

- [ ] Implement individual lighting and speaker tones
  through the existing owner and DEMO. Check incompatible equipment, rejected
  commands, timeouts, disconnects, stop/release and post-state.
- [ ] Compose the walk-around from verified lamp outputs. Check safe concurrent
  groups, access to each phase, duration, early exit and release when a stage
  fails partway. Require confirmed fitment and control return before live use.
- [ ] Add display link and RGB patterns, HVAC blower/flap controls, washer pumps,
  door and tailgate contacts, parking distances and horn. Admit exterior mirror, seat, window and
  powered tailgate movement only with verified bounds on lost communication.
  Recover guided learning and initialization procedures separately.
- [ ] Recover the TPMS measurement and equipment reads for supported variants.
  Check corner assignment, stale or missing sensors and incompatible equipment.
  Establish the F48 retrofit prerequisites from the exact hardware and vehicle
  order before proposing parts or coding.
- [ ] Decode stored parked-current cycle records, durations and additional wake-up
  history. Verify that the feature uses read-only requests and labels historical
  data and unavailable values explicitly.
- [ ] Recover like-for-like 12 V battery registration contracts, including the
  configured type/capacity, required inputs, power and ignition conditions, and
  before/after history. Verify the exact request, rejected or uncertain writes,
  unchanged or ambiguous history, and no automatic replay in DEMO.

## Later implementation choices

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
