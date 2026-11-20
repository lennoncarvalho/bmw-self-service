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

- [ ] During the next intended physical history append, compare the confirmed
  request and activation with the date and items shown in iDrive. Replacement
  remains physically unverified and requires an independently intended operation.
- [ ] Confirm live reconnect after a naturally interrupted read and Clear All
  results during an intended fault clear. Retain actual identities and outcomes.

Later: full-width DoIP feature addressing/newer releases, Advanced Coding,
validated deferred coding targets, additional DEMO profiles/DoIP simulation,
Windows/Intel Mac and packaged releases.
