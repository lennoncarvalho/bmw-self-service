# Implementation tasks

Work in priority order. Update these steps in place when the implementation
changes; remove completed detail instead of appending session or PR reports.
Current source contracts and reproduction routes are in [docs.md](docs.md).

## Stateful DEMO — next implementation milestone

Follow [approved behavior](plan.md#stateful-demo) and the
[integration boundary](docs.md#demo-migration-boundary). Complete D1–D7 in order;
later profiles, DoIP simulation and user-facing failure controls are out of scope.

- [ ] **D1 — Build one coherent vehicle fixture.** Select exact bundled HSFZ
  identities/software, vehicle order, native jobs and coding definitions that
  support every milestone workflow. Generate standalone initial wire data with a
  synthetic valid VIN, representative faults/details, service items, coding bytes
  and adequate power. Seed an isolated editable history draft separately from
  virtual headunit state. Done when each feature's existing selectors accept the
  same profile without guessed layouts, source-folder access or new feature gates.
- [ ] **D2 — Bind environment and persistence.** Add immutable live/DEMO session
  metadata and a DEMO vehicle-instance identity retained across reconnects.
  Update store selection, coding plans/writes/recovery/comparison, CBS intent and
  history preparation/journals to use that context instead of hardcoded live
  values or `.data` detection. Done when DEMO records support normal DEMO
  restoration/verification, cross-environment operations are rejected before send,
  and fresh instances cannot inherit prior consumed drafts or recovery locks.
- [ ] **D3 — Connect a local virtual vehicle.** Inject stream creation into
  `DiagnosticConnection.connect()`; wrap a local socket pair in `BoundedStream`
  and keep the existing HSFZ/UDS/native-job path. Give the virtual peer a bounded
  background lifecycle, addressed dispatch, sessions, ACKs and explicit unsupported
  replies. Supply only synthetic discovery; run normal VIN verification. Done
  when connection, keepalive, disconnect and close settle through one app protocol
  owner without physical discovery/network access, leaked threads or live fallback.
- [ ] **D4 — Migrate reads to normal workers.** Route Overview refresh, ECU
  identification, diagnostic memories/details/MIL, CBS and coding catalogue/value
  reads through their existing workers and native jobs. Remove direct fixture
  reads from pages and MainWindow. Done when the fixed profile produces complete
  supported coverage and consistent values, including engine faults and MIL,
  through normal loading, navigation and settled-result publication.
- [ ] **D5 — Execute stateful writes.** Implement exact profile-supported clear,
  CBS reset, coding authorization/group writes, restoration and history
  append/replacement responses in the virtual peer. Retain normal preparation,
  confirmation, source restrictions, durable records and write lockouts. Complete
  simulated cycles after source restart sequences; verify coding with fresh reads.
  Done when faults clear, service values change, coding survives reconnect and
  restores, and history sends produce checked normal journals without a reader
  or fabricated prior-history backup. Supported happy-path responses must reflect
  accepted requests and state, never blanket service acknowledgements.
- [ ] **D6 — Finish lifecycle and remove legacy DEMO.** Add Reset DEMO under the
  existing gear menu; block it during active work. Retire the connection before
  reseeding, refresh page/store contexts and reject stale callbacks. Preserve saved
  evidence; reset virtual state on app launch. Keep only environment badges and
  persistence routing outside the shared workflows. Done when mock categories,
  preview-only writes, `demo_cbs()` and the old MockConnection path have no active
  callers, with existing saved previews retained as non-restorable local data.
- [ ] **D7 — Verify the complete app.** In native macOS DEMO at 1720×879 and
  1024×700, exercise every supported page/action, confirmations, search, expansion,
  write/restore/verify, history append/replacement, reconnect, reset and restart.
  Check source restrictions and read-only behavior still apply. Use scratch
  offline checks for frame fragmentation, unknown requests, connection loss and
  cross-environment rejection; add no runtime failure UI or test framework. Review
  lifecycle/write changes and run full preflight. Done when no supported workflow
  uses a UI shortcut, real vehicle stores remain unchanged, no physical vehicle
  networking occurs and reset/restart reliably restores the same starting state.

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

- [ ] During the next intended physical history append, compare the confirmed
  request and activation with the date and items shown in iDrive. Replacement
  remains physically unverified and requires an independently intended operation.
- [ ] Confirm live reconnect after a naturally interrupted read and Clear All
  results during an intended fault clear. Retain actual identities and outcomes.

## Additional Overview readers

- [ ] Recover exact SOC, SOH and KL15 readers from the
  [source leads](docs.md#additional-display-reader-leads), validate native decoding
  offline and generate standalone assets. Add UI fields only when their readers
  handle quality, unavailable values and exact variant applicability.

Later: full-width DoIP feature addressing/newer releases, Advanced Coding,
validated deferred coding targets, Windows/Intel Mac and packaged releases.
