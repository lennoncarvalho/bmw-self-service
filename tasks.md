# Implementation tasks

Work in priority order. Update these steps in place when the implementation
changes; remove completed detail instead of appending session or PR reports.
Current source contracts and reproduction routes are in [docs.md](docs.md).

## CBS — complete for the current milestone

Implemented: manual native reads, strict record accounting, software/identity
preflight, exclusive foreground reset execution, durable journals, source-specific
DSC and routine sequences, stale-row reset revocation and uncertain-outcome
lockout. D94 now has an explicit historical job supplement and native start,
one-second delay, result query and post-read. Source selection is reconciled:
the eight additional readers are outside the standard workflow's primary groups
and remain observations. Same-item records from different primary ECUs retain
explicit owner selection; duplicates within one ECU stay blocked. Compiler,
native-worker, fragmented protocol-owner and Qt checks cover these boundaries.
Captured distance sentinels are suppressed in both native-result and fallback
decoding. Other source-supported owners retain offline verification; this is
not universal vehicle acceptance.
No implementation or owner-car acceptance step remains open for this milestone.

## Diagnostic details and clearing — source implementation complete

Implemented: native fault/information detail jobs selected by fault code,
occurrence/healing counters, recorded mileage/time and source-scaled environment
values in always-visible cards. Preserve every recorded state, source units and raw
results. Time counters have no invented calendar epoch or first/last labels.
Basic lists settle before bounded details; failed details retain collected codes.
Native optional-table trap handling supports environment decoding. Offline native,
worker/error and Qt checks cover these boundaries; physical behavior is unverified.

Memory coverage follows the loaded variant's readers, including permanent memory;
native record accounting retains partial codes without claiming a complete scan.
Clear All includes every target disposition, continues after definite rejection,
stops on uncertainty/stream failure, and preserves reread counts and remaining
faults. UI outcomes survive refreshes, with thread-exit lockout and no automatic
retry or reread after a stopped batch. Native, fragmented/pending protocol-owner,
failure and Qt flows are verified offline; no physical clearing is claimed.

## Easy Coding readiness

- [ ] Resolve disabled presets when source definitions establish the missing
  function mappings or compatible values. Eligible features already expose
  their representable choices. Extend exact G26 type coverage with a source
  that identifies the unlabelled type keys.
- [ ] Verify a live supported coding change and explicit restore after any required
  cycle. From Backups, run **Verify coding after vehicle cycle** on each completed
  operation and retain the session log and comparison. Response-confirmed
  outcomes remain separate from observed verification.

## History and integrated acceptance

Implemented: local JSON editor/workspaces, sourced service types and multi-item
cards, separate journals, append/replacement workers and exact headunit contracts.
Offline checks cover the 12 native job profiles, ordered writes, failure handling,
JSON and VIN isolation, foreground lockout and retained evidence export.

- [ ] During the next intended physical history append, compare the confirmed
  request and activation with the date and items shown in iDrive. Replacement
  remains physically unverified and requires an independently intended operation.
- [ ] Confirm live reconnect after a naturally interrupted read and Clear All
  results during an intended fault clear. Retain actual identities and outcomes.

Later: full-width DoIP feature addressing/newer releases, Advanced Coding,
validated deferred coding targets, Windows/Intel Mac and packaged releases.
