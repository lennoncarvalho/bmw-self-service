# Service history — local JSON, append and explicit replacement

Status: approved product scope consolidated 2026-10-29; local JSON/editor and
isolated workspace persistence, history-operation journal and mode-specific write
workers implemented. Physical validation remains pending. Authority: D-50–D-55 in
[owner decisions21](21-product-decisions.md).
This supersedes earlier history-read/complete-car-backup gates in spec 26, plans,
tasks and skill examples. [Native/PRG evidence](evidence/task-b-history-deep-investigation.md)
and [additional-source comparison](evidence/task-b-history-new-sources.md) retain
actual findings; scope withdrawal is not a universal protocol impossibility claim.

## What the page represents

The history page is a **local service record editor and writer**, available
without a connection. On connection, identify the vehicle/headunit but issue no
history read, DID scan or routine-result discovery probe. Label the list “Local
service records” and explain: “Existing vehicle history cannot be read. These
records come from this app or an imported JSON file.” An empty local list never
means the car has no history. Reconnection never fills the list from the car.

Keep one vehicle's known records and pending drafts together with clear origin
and operation outcomes. Imported records and earlier response-confirmed writes
remain local evidence, not a synchronized vehicle archive. Switching VIN or
DEMO/live mode must not silently reuse another vehicle's drafts or outcomes.

| Action | Input and request sequence | Explicit limit |
|---|---|---|
| Append entry (default) | One dated entry with 1–13 items; ADD only, followed by an evidenced activation/reset step if required | Never send ERASE; no guarantee about unseen dates or a full headunit. Capacity rejection never triggers replacement. |
| Erase and replace | User-reviewed nonempty local replacement list; ERASE once, ADD each entry in the frozen preview order, evidenced activation/reset if required | Deletes the car's current list, including entries absent from this file. No backup/restore of that unreadable original is available. |

Local draft entries may be edited/deleted to prepare a list. These actions never
change the car. There is no standalone erase button or per-record car edit/delete.
An empty replacement is blocked; it is not an accidental erase-all operation.
Append is one entry per confirmed operation, not a hidden batch of old records.
Do not automatically sort by mileage: backdated/conflicting mileage is allowed,
and replacement order must be visible and fixed in the preview.

## Confirm, persist, execute and report

1. Validate the complete proposed operation before any request: verified VIN and
   supported exact headunit/encoder, dates/items/field widths, source-supported
   prerequisites, connection ownership and power policy D-31. No current odometer
   query. Existing car history being unavailable is **not** a history write gate.
2. Show mode, target VIN/headunit, entry/date/mileage/garage/items, count/order,
   activation instructions and power/definitive-write responsibility. Append
   confirmation discloses unavailable old-history backup and unseen duplicates.
   Replacement requires explicit acknowledgement that records not included will
   be permanently lost; it must not be armed by import metadata or a hidden default.
3. Before sending, durably save an immutable local snapshot, intent and exact
   request plan with operation ID, target identity, encoder identity/hash, mode
   and timestamps. Record `vehicle_history_before: null` and its unavailable
   provenance. Do not fill this with local records, an empty list or invented ECU
   bytes. Persistence failure blocks sending. Keep all local snapshots/journals
   until explicit deletion, as D-41 requires.
4. Freeze the operation and use one CarWorker/Task A owner. Block edits, imports,
   navigation, disconnect, competing requests and normal close; no write Cancel.
   Keep progress responsive. Use at most 30 seconds per request under a published
   five-minute overall operation deadline including queueing, delays and reset.
   Validate that the plan fits; stop with remaining steps unattempted on exhaustion.
5. Check exact routine/subfunction echoes, reply shape and variant-bound business
   status, not just transport ACK or positive SID. Preserve raw requests/replies,
   each accepted/rejected/unattempted step and the point at which effects become
   uncertain. If journal persistence fails after a car step, stop all subsequent
   mutations, retain any in-memory response for display/export and report which
   effects occurred or are uncertain; do not keep sending without durable results.
   Stop the history operation on failure; never continue a replacement
   after an unresolved/rejected step. Do not treat a reset-disconnect as success
   without its own evidenced completion contract.
6. All accepted steps produce **response-confirmed** completion, with required
   ignition-off/on or headunit-cycle instructions and a request to inspect iDrive.
   Do not show “read back”, “synchronized” or “vehicle verified”. If entries were
   accepted but activation fails, retain that partial state, not “nothing written”.
   The local journal/card can show previously accepted requests without claiming
   that the car still contains them. Keep draft, accepted, rejected and uncertain
   records distinct; imported outcome claims never become live authorization.

After a timeout/cable/process interruption, never replay ADD, resume a replacement
at a guessed index or roll back automatically. Reidentify VIN/headunit and show
last known results; ask the user to inspect iDrive before a separately confirmed
new action. A deliberate replacement from a local file can reconstruct only
that supplied list, not recover unknown erased history. Coding retains its own
complete ECU baseline, meaningful reread and restoration requirements.

## Local records, date rules and service types

New entries and every record proposed for sending must have a valid nonfuture
calendar date. Block a new date already in the vehicle-bound local project,
known prior-operation records or pending drafts; the edited record excludes its
own draft identity from this comparison, never a prior journal entry. Only an
unsent draft is eligible for Append: accepted/uncertain cards are not resendable
drafts. Unknown dates in the car cannot be checked:
state this limitation rather than pretending a file is a complete scan.

Imports retain conflicting/unsupported records for preview/export. A replacement
write list must have no duplicate dates **within that list**; dates already in
the prior local ledger are allowed because replacement intentionally rewrites
those records. Do not run each replacement item through append-only existing-
date rejection. Require explicit user resolution of within-list conflicts without
automatic removal, merging or plus/minus-one-day shifts. Append never requests
ERASE or replacement; exact ECU capacity/eviction behavior still needs validation. Future imported records
remain in the file but cannot be sent. Mileage is entered by the user, in native
km with unsigned32 bounds; do not enforce chronology or query current mileage.

Use these fourteen service types, corroborated by the Java code/label arrays and
OSS source (decimal IDs below). A dated entry has1–13 items; fourteen available
types is not a fourteen-item wire capacity.

| ID | English selector label |
|---|---|
| 1 | Engine oil |
| 2 | Front brakes |
| 3 | Brake fluid |
| 4 | Microfilter / cabin filter |
| 5 | Recirculating air filter |
| 6 | Rear brakes |
| 10 | Spark plugs |
| 11 | Engine air filter |
| 12 | Fuel filter |
| 100 | Vehicle check |
| 20 | Pre-delivery inspection |
| 21 | Running-in check |
| 32 | Statutory vehicle inspection |
| 33 | Statutory emissions test |

No separate oil-filter code 4, coolant0x12 or transmission0x23 choice is allowed
without new evidence. No evidenced free-text **service type** exists: do not
invent Custom, transmit labels as IDs or silently fall back to engine oil.
Garage/name text is a separate supported field: up to 7 ASCII bytes without NUL,
right-padded on the wire; preserve the explicit BMW/independent flag. Reject
unencodable input without replacement/truncation. Apply the recovered correction,
status and item field bounds. Keep signed remaining-distance argument semantics
for the current PRG-backed encoder until variant evidence resolves the differing
unsigned/display interpretation. Never hide unknown imported numeric values or
coerce them to a known service; keep them in the file and block unsupported sends.

## Multi-item cards — required UI task

Use QScrollArea/widget children and inline expansion. Each collapsed card shows
calendar date, regionally formatted mileage/unit, garage, record status, compact
service-item chips/count, and a local draft/imported/previous-response state.
Expansion exposes every item's name or unknown ID, status and relevant distance/
time fields. A write of one card sends all its items as **one** record. Edit/remove
controls act only on local drafts; the page does not imply editing a car record.
Unknown/import-conflict states are visible and editable without data being dropped.
Publish the initial local page batch together; perform no vehicle read to draw it.

## File interchange — JSON only

Import/export one ordinary unencrypted versioned JSON document. No .bmwsh, .tst,
QR, conversion adapters, proprietary file support or auto-executed job files.
Legacy parser/serializer helpers currently in app/service_history.py should be
retired from the runtime API; retain their source-format findings in research.

Minimal v1 structure (native units and ISO calendar dates; presentation locale
never changes the file's numeric/date meaning):

```json
{
  "schema_version": 1,
  "vin": null,
  "entries": [
    {
      "date": "2026-10-20",
      "mileage_km": 65000,
      "dealer": "OWNER",
      "dealer_flag": 0,
      "correction": 0,
      "status": 1,
      "items": [
        {"code": 1, "status": 1, "remaining_distance": 0, "remaining_time": 0},
        {"code": 11, "status": 1, "remaining_distance": 0, "remaining_time": 0}
      ]
    }
  ]
}
```

`vin` may be null for an offline draft or a valid17-character VIN. Treat an
unbound file as unbound until the user associates it with the connected car.
A different bound VIN blocks sending that project; intentional copy to another
vehicle is an explicit operation retaining source provenance, never silent reuse.

Reject malformed JSON, duplicate object keys, unsupported schema versions,
nonfinite/fractional values where integers are required, wrong types and oversized
files (1 MiB resource limit, not a car-capacity claim). Validate all entries before
replacing the current local project; a bad import leaves it intact. Distinguish
structural/schema errors from visible semantic conflicts such as unknown item IDs,
duplicate dates and future entries: retain validly structured conflict data for
preview/export, disable affected sends, and never silently filter or normalize it.
Preserve unrecognized fields on same-version round-trip; unknown versions are not
silently upgraded. Do not add mode/erase directives or authorization flags to this
interchange format. Import is data-only, makes no car request, never selects
replacement mode and cannot overwrite an open project without an explicit action.
Export is deterministic and atomic with write errors reported; support movement
between computers and exact field round-trip. User-requested export overwrite
is explicit. Operational outcomes/provenance live in the journal, not forged
vehicle-verification flags in the interchange file.

## Storage and implementation boundaries

app/service_history.py owns models, the sourced catalogue, validation, exact
variant-bound encoder/results and a frozen append/replace plan. Add
app/history_files.py for the simple project JSON and a separate history journal
store using durable atomic publication. UI remains in ui/service_history_page.py;
car I/O lives in a CarWorker subclass using Task A APIs.

Keep the existing operation-store v1 coding schema/validator intact. History uses
its own version 1 JSON journal, not a fake coding baseline or a loosened validator.
The journal records kind=history-operation, operation ID/mode/target/encoder,
vehicle_history_before=null, immutable local_before and intended entries, exact
request plan, source provenance and ordered outcome events. Hash its immutable
intent and full record for accidental-corruption checks; no signature/encryption.
Persist prepared/sending/response-confirmed/cycle-required/partial/uncertain
states with per-step responses/unattempted work. Never emit readback-verified for
history. Retain old coding files and history journals through explicit deletion.

Interchange exports only the minimal project JSON, not vehicle-verification or
mode flags. Journal export remains a separate troubleshooting/local preservation
file. Reuse or extract the existing durable publication primitive (temp/fsync/
atomic replace/directory fsync), keeping feature validators separate. Backups UI
routes the explicit journal kind and labels local history preservation honestly;
no restore button promising unknown prior car history. This is the selected
storage design, not a pending owner or implementation choice.

## Acceptance and remaining facts

The runtime page, local storage, separate operation journal and mode-specific
append/replacement workers are implemented. Exact identity/prerequisites, durable
per-step outcomes and checked application responses gate execution; physical
validation remains pending. See [implementation](../tasks/task-b-history-write-implementation.md)
and [source-backed execution contract](evidence/task-b-history-write-contract.md).
B-HIST-R is retired and must not be resurrected as a release prerequisite.

Offline/manual checks: JSON round-trip/errors/conflicts/unknowns/VIN/atomic I/O;
all fourteen choices and 13-item boundary; no custom fallback; date rules with an
empty known-local ledger; card expansion; ADD-only plan has no ERASE; replacement
has exactly one ERASE and all reviewed records in order; frozen plan/lockout;
status/echo/timeout/reset failure and durable partial/uncertain results; no replay.
No automated suite/tests directory. Full Ruff lint/format/mypy before each push.

Owner car acceptance uses a concrete reviewed procedure: append and inspect in
iDrive; explicit replacement only with the user-reviewed list and irreversible-
loss acknowledgement. Record exact headunit/software, wire results and observed
on-screen outcome separately. Unknown headunit capacity/order/session/reset
facts remain research/validation work; a capacity rejection must never auto-erase.
Missing coding/MIL/DoIP work still keeps Task B open. No universal BMW claim.


## Local editor implementation checkpoint — PR16 continuation

`app/history_files.py` implements v1 project parsing/validation and deterministic
compact atomic export. Limits are1MiB,1000entries,255 structurally preserved items
per entry, depth16,50000nodes and4096characters per string. Sendability remains
1–13items with sourced numeric/ASCII/date rules. Imported future/unknown/status/
duplicate records remain visible/exportable; editing does not silently normalize
their values. Existing future dates may remain unchanged while resolving other
conflicts; a newly chosen future date cannot be saved. Unknown fields are retained.

`app/history_workspace.py` stores separate hashed local editor envelopes under
`~/BMW-Tool/history/projects`: offline, live-VIN, demo-VIN and demo-unbound (the
supplied DEMO fixture has only a short identifier). Full-record integrity hashes,
stable draft IDs and import/copy provenance are separate from interchange data.
These editor envelopes are **not** mutation journals or coding backups. No
accepted/uncertain outcomes are manufactured from imported claims. Explicit VIN
association preserves original source VIN/workspace; loading never rebinds a file.

The Widgets page works offline, uses25cards per page in original file order,
expands all item values and provides local edit/remove/import/export/reload.
File work runs in retained background workers; stale modal actions are rejected,
corrupt initial state cannot silently become an editable empty fallback, and
shutdown waits nonblockingly for one worker owner. Coding validators stay intact.

See [implementation and verification](../tasks/task-b-local-history-implementation.md).
The subsequent B5b/B4 history extension implements the separate operation journal,
prior-operation date accounting, frozen append/replacement plans, business results
and write completion/reset handling; physical validation remains pending. See
[the implementation](../tasks/task-b-history-write-implementation.md). CBS read/write
follows history and precedes coding under D-58.
