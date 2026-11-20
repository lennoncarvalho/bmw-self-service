# Product plan

BMW Self Service is a personal-use desktop application for source-supported
BMW F/G/U/I vehicles over an ENET cable. The current milestone is functional
macOS use from Python source with the supplied ISTA 4.29/HSFZ contracts.
Windows, Intel Mac, packaging/signing and newer transport releases come later.
Only the owner's F48 X1 MY2018 with NBT is available for physical observations;
that is neither the product boundary nor a dependency for other source work.

## Delivery order

| Priority | Required outcome |
|---|---|
| CBS | Reliable manual service-status reads and individual supported resets, correct ECU ownership, complete decoding and honest completion/failure handling |
| Diagnostics | All supported ECU/memory faults, useful occurrence/environment details, complete Clear All accounting and current engine fault indication |
| Easy Coding | All applicable source presets, actual current values, enforced deferred-target restrictions, complete backups and checked write/restore |
| History and integration | Reliable local JSON records, ADD-only append and explicit replacement; coherent connection, loading, interruption and recovery across features |

Source recovery must lead to implementation and verification. Research notes,
DEMO output and static checks alone do not complete a feature. Unfinished
implementation stays in [tasks.md](tasks.md); reusable facts belong in
[docs.md](docs.md). Do not keep parallel status documents or PR/session histories.

## Required behavior

### Connection and display

- Physical Ethernet and Wi-Fi adapters may be selected for IP-based discovery;
  exclude virtual/internal networking interfaces. No Bluetooth, K+DCAN or E-series scope.
  Discover the transport and exact identities rather than infer them from year
  or chassis. Scope discovery to the selected Ethernet adapter. Refuse multiple
  responding vehicles instead of picking the first one.
- Verified VIN and diagnostic communication enable vehicle operations. Without
  verified VIN, provide connection details/logs for limited troubleshooting.
  Failed optional reads preserve a valid connection and show unavailable data.
- Publish each page's initial batch together. Foreground work shows a loading
  indicator/backdrop and blocks competing actions; failures remain visible
  according to each feature's display rules.
  One main window, inline details and a single outer scrollbar per page.
- Reuse consistently styled Qt date and selection controls across forms, with
  configurable bounds, regional formatting and option lists. Popups must remain
  opaque, expose every option through normal scrolling and support keyboard use.
- English interface. Prefer English diagnostic descriptions, but keep all fault
  codes visible with available source-language text or no description. Conflicting
  descriptions never justify guessing or dropping a fault. Use the system region
  for dates/numbers, Brazilian regional formatting and kilometres as fallback.
- DEMO is explicit and never grants live write authority. Diagnostic logs retain
  full identifiers, including VIN, and DEBUG request/reply bytes.

### Stateful DEMO

- First milestone: one coherent source-backed HSFZ vehicle profile covering
  Overview, diagnostic reads/clearing, CBS reads/resets, Easy Coding, backups,
  restoration/verification and history append/replacement. Additional profiles
  and DoIP simulation come later; existing unsupported features stay unavailable.
- Ship a fixed starting set of representative faults, service items and coding
  values. Successful supported actions produce visible results through normal
  workflows. Do not randomize each connection or expose failure-injection UI.
- Keep virtual vehicle changes across disconnect/reconnect within the app run.
  Restarting the app or explicit Reset DEMO restores the bundled vehicle state.
  Saved DEMO backups/journals remain separate from this volatile vehicle state
  and are not deleted by reset. Fresh instances must not inherit stale caches,
  consumed-draft markers or recovery locks from earlier DEMO instances.
- Simulate the vehicle at the communication boundary. Use the same connection
  facade, protocol owner, transport parsers, UDS services, native jobs, readers,
  write preparation and execution as live sessions. Pages consume normal worker
  results; remove direct fixture access and separate preview-only workflows.
- Simulated writes change virtual ECU state and subsequent reads observe it.
  Exercise fault clearing, CBS resets, coding/restoration and history
  append/replacement with their existing confirmations, power policy, durable
  state where required by the feature, application-response checks and uncertainty rules.
- Complete simulated activation/cycles automatically after the normal source
  restart sequence; add no cycle control. Verification still performs fresh
  reads and records observed simulated state separately from response completion.
- History uses normal application results with temporary in-memory outcomes.
  Prior headunit history remains unavailable; add no virtual iDrive view or
  history-read capability.
- Keep the DEMO label and explicit environment metadata for session composition,
  logging and persistence. Isolate simulated workspaces, backups and journals;
  never allow a DEMO record to authorize a live operation or the reverse.
- DEMO must work without a car or source folders. Bind its connection to a local
  virtual peer with no physical discovery or fallback to a real vehicle. Select
  the environment before connecting; do not replace an active session in place.
  Reset is explicit and unavailable during vehicle work; retire the old connection
  before replacing state and invalidate its queued results and page caches.
- Match simulated identities, software and payload layouts to bundled source
  definitions. Unsupported requests remain explicit; simulated success is not
  physical validation or evidence of broader source support.

### Diagnostics and CBS

- Read all identified supported ECUs/memories with explicit failed/unattempted
  coverage. Empty partial results do not mean the whole car is healthy.
- Provide one Clear All action, available for supported targets even with
  incomplete coverage; disclose gaps, continue after definite local rejection on
  a usable stream, and reread. No per-code/per-ECU clear UI, backup or saved-report
  prerequisite. Permanent faults have no separate erase action.
- The engine indicator follows present or confirmed engine fault memory,
  independently of engine-running state. Red for present/confirmed faults, green
  only after complete supported engine reads without them, grey when unavailable.
- CBS is a manual read followed by a separately confirmed single-item reset.
  Start with no service rows; display results directly after reading, without a
  show/hide control. No generic erase-all, automatic reset, history erase
  substitution, duplicate-owner guessing or observational-source reset authority.
  Failed refreshes retain clearly stale values with reset disabled.
- CBS cards show available due values on a small first line, followed by the
  larger service name, one reported-percentage bar and smaller reset counts and
  forecast intervals. Hide technical source listings and repeated descriptions;
  keep actionable warnings. Dates and distances are optional and independent;
  never substitute forecast intervals for current remaining values.

### Coding and writes

- Easy Coding shows named sections, features, and options with the observed
  value selected. Opening a section reads its uncached ECUs on demand, requesting
  only groups used by their named options. Presets excluded by the source for
  the identified model are hidden and skipped. Reopening cached options performs no
  vehicle I/O. Display reads are not backups; preparation still requires fresh
  complete baselines. Unavailable features stay in their sections, disabled and
  excluded from writes. Catalogue failures without section data go to the log.
- Recover applicable presets and byte layouts from supplied definitions. Keep
  exact reported identity separate from a layout chosen by the source's proven
  compatibility rule. Display unmatched current values as Custom and preserve
  their original bytes unless the user selects a supported change.
- Advanced editing and unvalidated safety-ECU coding are deferred. Enforce coding
  scope in preparation, writing and restoration; do not turn that into a blanket
  ban on diagnostics, clearing or legitimate CBS operations at those addresses.
- Coding requires a complete vehicle baseline and complete original data for
  each target, immutable intent, exact definition/software, confirmation and power
  checks. Source flags alone do not authorize a write. CBS retains its own local
  intent/results. History uses confirmed in-memory intent without a coding baseline
  or saved operation journal.
- No write Cancel. Block disruptive navigation, disconnect, competing operations
  and normal closing during mutation/check/recovery. Block known insufficient
  power; when reliable power readings are unavailable require acknowledgement.
- A transport ACK is insufficient. Check final application results and meaningful
  post-state; report response-confirmed separately from observed verification.
  Respect source-required activation/cycles instead of demanding universal
  immediate readback. Uncertain outcomes never trigger automatic replay,
  resume or rollback. Easy Coding's established failures use the evidenced
  recovery path; failed recovery remains explicit.
- Keep backups/journals until explicit user deletion; support portable unencrypted
  file export/import. Imports are data, never write authorization. Recheck vehicle,
  software, definitions and current state before a separately confirmed restore.

### Local history

- Show compact service entries with their item details always visible and distinct
  unwritten, accepted and uncertain states. This page is a temporary staging area:
  discard its entries on page exit, disconnect or app close, without save prompts.
  Volatile duplicate-date and uncertainty guards survive page changes within
  the same connection; disconnect or an environment change clears those guards.
  No autosave, automatic project loading or history operation journals. Keep
  **Load from file**, **Write to file** and **Write to car** visible; align car-write
  buttons to the right and style them red. Use a larger two-column entry form
  and a three-column item selector (checkbox, title, completion). Hide individual
  remaining distance/time controls and columns. Use source labels for completion,
  not raw numeric codes. Hide the correction field: new entries use zero;
  imported values remain preserved.
- Keep staged entries in descending mileage order, including after additions,
  edits and file loads. Keep each entry's identity and write state attached when
  sorting; file output and replacement follow the displayed order.
- JSON only, useful offline. Existing car history cannot be read or backed up;
  do not pursue a reader, hidden probes, legacy adapters or fabricated readback.
- Each **Write this entry** appends that one staged entry with ADD only. The top
  **Write to car** erases previous car history and writes every staged entry in
  frozen order, including entries already appended individually. Warn and confirm
  before either car write; replacement must explicitly disclose irreversible loss
  of omitted entries. No automatic write, silent replacement fallback, standalone
  erase or direct editing/deleting individual car entries.
- Freeze exact intent/requests and retain per-step outcomes in memory through the
  operation. Only explicit **Write to file** persists the entry list. Prior car
  history is unavailable, never an empty backup. Report checked application
  completion and required activation/iDrive inspection; do not retain write journals.
  Keep full per-step outcomes in memory until staging clears, distinguish rejected
  and unattempted entries, and show partial-write instructions before asking to
  reconnect after a dropped connection. Previously sent dates remain editable for
  full replacement, with individual append disabled and explained before preparation.
- Valid nonfuture dates; reject duplicate new dates against known local/pending
  records and duplicates within a replacement list. Unseen car dates cannot be
  checked. Keep imported conflicts/unknown fields visible and exportable; never
  silently drop, merge or change their values. New and edited entries must have
  strictly increasing mileage between different dates. For any two staged entries,
  the later date must have higher mileage. Equal mileage on different dates is a
  conflict. Show friendly validation messages while keeping the form open.
  Imported conflicts remain visible and
  exportable, with affected car writes blocked until corrected. Do not constrain
  entries by a current-odometer read or claim knowledge of unreadable car history.
  Use the sourced service types/field limits in [docs.md](docs.md#history-data).

## Validation boundary

Implement broad source-supported branches without waiting for other vehicles.
Separate source contracts, working code, offline verification and physical
observations. Ask the owner for targeted car logs only at a concrete blocker
that those logs can resolve, with a purpose and reproducible read-only steps.
Do not perform gratuitous resets, erases or coding writes for testing.
