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
  indicator/backdrop and blocks competing actions; failures remain visible.
  One main window, inline details and a single outer scrollbar per page.
- English interface. Prefer English diagnostic descriptions, but keep all fault
  codes visible with available source-language text or no description. Conflicting
  descriptions never justify guessing or dropping a fault. Use the system region
  for dates/numbers, Brazilian regional formatting and kilometres as fallback.
- DEMO is explicit and never grants live write authority. Diagnostic logs retain
  full identifiers, including VIN, and DEBUG request/reply bytes.

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
  Expansion performs no I/O. No generic erase-all, automatic reset, history erase
  substitution, duplicate-owner guessing or observational-source reset authority.
  Failed refreshes retain clearly stale values with reset disabled.

### Coding and writes

- Easy Coding identifies catalogues first. Read current values when an ECU is
  opened, requesting only groups used by its named options and caching them for
  that connection. Reopening cached options performs no vehicle I/O. Display
  reads are not backups; preparation still requires fresh complete baselines.
- Recover applicable presets and byte layouts from supplied definitions. Keep
  exact reported identity separate from a layout chosen by the source's proven
  compatibility rule. Display unmatched current values as Custom and preserve
  their original bytes unless the user selects a supported change.
- Advanced editing and unvalidated safety-ECU coding are deferred. Enforce coding
  scope in preparation, writing and restoration; do not turn that into a blanket
  ban on diagnostics, clearing or legitimate CBS operations at those addresses.
- Coding requires a complete vehicle baseline and complete original data for
  each target, immutable intent, exact definition/software, confirmation and power
  checks. Source flags alone do not authorize a write. History and CBS use their
  own local intent/results rather than a fake coding baseline.
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

- JSON only, useful offline. Existing car history cannot be read or backed up;
  do not pursue a reader, hidden probes, legacy adapters or fabricated readback.
- Append one unsent multi-item entry with ADD only. Explicit erase-and-replace
  uses a reviewed nonempty list in frozen order and warns that omitted existing
  entries are irrecoverably lost. No silent replacement fallback, standalone erase
  or direct editing/deleting individual car entries.
- Preserve local state, exact intent/requests and per-step outcomes before and
  through writes. Prior car history is unavailable, never an empty backup.
  Report checked application completion and required activation/iDrive inspection.
- Valid nonfuture dates; reject duplicate new dates against known local/pending
  records and duplicates within a replacement list. Unseen car dates cannot be
  checked. Keep imported conflicts/unknown fields visible and exportable; never
  silently drop, merge or shift them. User-entered mileage is not constrained by
  chronology or a current-odometer read. Use the sourced service types/field limits
  in [docs.md](docs.md#history-data).

## Validation boundary

Implement broad source-supported branches without waiting for other vehicles.
Separate source contracts, working code, offline verification and physical
observations. Ask the owner for targeted car logs only at a concrete blocker
that those logs can resolve, with a purpose and reproducible read-only steps.
Do not perform gratuitous resets, erases or coding writes for testing.
