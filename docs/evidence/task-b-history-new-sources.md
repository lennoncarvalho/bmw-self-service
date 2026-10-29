# Additional history sources — 2026-10-29

**Product scope supersession (2026-10-29):** D-50–D-55 retire headunit history
reading and the complete car-history baseline/backup prerequisite. These source
findings remain historical evidence; reader searches and legacy-file adapters
below are no longer requested work. Current behavior is local **JSON only**,
ADD-only append or explicit irreversible erase-and-replace, per
[workflow28](../28-service-history-workflow.md). No runtime worker is newly
enabled by this planning change; coding baseline requirements remain intact.

**Primary implementation references, static inspection only.** This investigation
answers the owner's request to inspect devttys1/bmw-service-manager and the new
Java package. No app behavior changed, dependency was installed, target app was
run, or car request was sent. The current history write guards remain active.

## Result

Both sources help with **writing** and presentation; neither supplies a recovered
complete headunit service-history reader. This conclusion concerns the inspected
versions, not every possible software/vehicle implementation. CBS current-service
reads and generic job-result reads must not be presented as a headunit archive.

| Source | Read finding | Write finding |
|---|---|---|
| [bmw-service-manager](https://github.com/devttys1/bmw-service-manager/tree/6c0041bb71674ec52d567c4a6360b5469c048173) | README explicitly says the car's history cannot be read back; headunit.py has experimental probes, not an implemented history reader | HSFZ headunit0x63, optional erase3101A080, ADD3101A081 per record, optional reset1101; supports constructing an ADD-only plan |
| `sources/BMW-HU-ServiceManager/HU-ServiceManager.jar` | Main/controller/FXML and packaged application classes expose identity/result reads, not a service-list read | G_MMI group jobs IDENT, STEUERN_SERVICEHISTORY_ADD, STEUERN_SERVICEHISTORY_ERASE, STEUERGERAETE_RESET through an external native diagnostic library |

ADD without a preceding ERASE is a useful lead in both sources. A source code
path that sends it does not establish capacity handling, ordering, same-day
collision behavior, or preservation on the owner's exact headunit. It also does
not provide the complete fresh baseline/backup required by D-32/D-35 and spec26.
Do not enable writes by treating a manually imported list as an observed car list.

## Reproducible identities and method

OSS commit: `6c0041bb71674ec52d567c4a6360b5469c048173`, dated
2026-10-24. Eleven selected original source/README/license files were fetched
through the GitHub connector and checked byte-for-byte against upstream Git blob
IDs. No project installation, startup, external test suite or simulator ran.
The source README reports development on an F48/NBT Evo and says other cars have
not all been tried. It is not all-BMW acceptance or validation of the owner's NBT.

JAR:1,116,122bytes, SHA-256
`299cf13ac1e16bd5da0c47850e7dbfe369d8c58712c58977dfa5fc618ab69e41`.
The actual window title in `sample.Main.start` says0.2beta; the launcher comment
says0.1beta/2017, so these labels are not interchangeable artifact identities.

REA opened/inventoried the JAR as ZIP, without an analysis-engine installation.
The archive has862central-directory members; the inventory includes duplicate
directory occurrences, so some parent relationships are explicitly unresolved.
Evidence parent `ev_fbd1787931aa8bbc9fde6485c7a5ed4824473a3cc9da418d4151d51c5a70fda8`,
summary `ev_4fe1b6f3449457ee8f96cb2efdc16f2909afa4c9e77de9a4a23107a74db54320`.
Full bundle was exported before closing. Existing Homebrew JDK21.0.13 `javap -p -c`
then disassembled all54`sample/` and `com/bmw/` application/wrapper classes
(out of661total classes). This is static JVM bytecode,
not decompiled Java or execution. FXML/localization and each class hash were kept.
No JavaFX application or JNI initializer was loaded. The macOS `/usr/bin/javap`
shim lacked a registered runtime; the already installed JDK was used directly.

[Manifest and local retained report hashes](task-b-history-new-sources-manifest.json)
locate complete bytecode, selected original sources, application class hashes,
handler summaries, the freshly re-parsed PRG result tables and comparison checks.
Raw proprietary classes, third-party code and personal vehicle data are not added
to the app/repo. REA remains development-only.

## Java call chain

Manifest main class `sample.Main` → `start` loads `/sample/sample.fxml` →
`sample.Controller`. Controller's four diagnostic call sites are:

| Method | JVM instruction offsets | Arguments/result |
|---|---|---|
| `connectToHU` | ldc G_MMI15, ident17, apiJob26 | Identifies the group; parses OBJECT from the returned job-result text into `ecu` |
| `writeToHU` | G_MMI82, ADD84, apiJob93 | Concatenates header/item semicolon job arguments, removes a trailing separator, invokes ADD |
| `deleteAll` | G_MMI110, ERASE112, apiJob122 | Separate explicit confirmation, then ERASE |
| `restartHU` | G_MMI11, RESET13, apiJob23 | Separate reset action |

These offsets are within each method's Code attribute, not native addresses.
Only ADD/ERASE service-history job-name strings occur in the scanned application
bytecode. The bundled generic diagnostic wrapper can invoke arbitrary supplied
jobs, which is not itself a recovered service-list reader.

`com.bmw.cascade.pruefstand.ediabas.Ediabas.<clinit>` calls
`System.loadLibrary("apijav32")`. apiInit/apiJob/apiResult methods are native.
The supplied folder contains no matching native library or job database. The
launcher prepends Windows diagnostic-installation directories. Thus this JAR is
an external-engine frontend, not a standalone cross-platform protocol engine.
Its job names route back to the PRG investigation already retained in this repo.

Dealer constructors Controller$3/$4 pair1=BMWdealer,0=independent. Dealer name
is limited to7characters by `connectToHU`. Item-code/English-label constructors
Controller$11/$13 independently corroborate the OSS catalogue below. The Java
form offers10item controls; the recovered PRG/wire limit remains13, so do not
copy the Java frontend's lower limit.

## Confirmations and contradictions

The independent review corroborated the main conclusions, exact catalogue and
ADD-only lead. It also notes that the OSS write implementation explicitly derives
from SHM, so agreement is not independent physical vehicle evidence.

1. **Record encoding agrees:** OSS `records.py` uses header `>BBHBIB7sBB`, a
   nineteen-byte header and seven-byte padded ASCII dealer field, matching our
   fixed-slot codec and actual .bmwsh sample. Thirteen items per record remains
   the encoded new-entry limit. No new vehicle-list read follows from this.
2. **Application status conflicts:** OSS `headunit.py`26–35/76–80 treats00and01
   as accepted, labels01EverythingOK/02outofmemory/03inconsistency and accepts a
   reply shorter than5bytes as success. Fresh parsing of the exact hash-matched
   CIC/NBT/NBTEVO/HU_MGU PRGs still yields00OK,01outofmemory,02inconsistency,
   04nopermission,05unknown. The repo's live-observation comments provide no full
   matching capture/software identity to resolve all variants. Our current
   table-backed decoder remains unchanged. Do not silently accept01or missing
   status, and verify routine/subfunction echoes as well as the positive SID.
3. **Distance interpretation conflicts:** OSS `records.py` uses unsigned BE32
   remaining distance and describes a live Evo display using status for lateness.
   Our PRG argument recovery uses signed32. Both encode identical bits for the
   nonnegative shared range; display meaning and out-of-range inputs need exact
   variant/capture evidence. Preserve all original bits; do not normalize old
   records or adopt a universal semantic change from the comment.
4. **Status labels differ:** Java calls status3overdue, while the OSS overall
   record status3saysincomplete. Item/record display semantics need separate
   source/variant checks; don't overwrite a known raw value to fit a label.
5. **Transport is a reference, not a replacement:** OSS `hsfz.py.request`
   correlates addresses but checks only positive SID, not echoed DID/routine,
   and renews pending/receive timeouts rather than using our absolute request
   deadline. Replacing Task A's owner/transport with it would regress guarantees.
   Its session42 and broad DID/3103 probes are research leads, not recovered
   history reads or permission to scan the owner's car during this task.

## Concrete service catalogue correction

Two sources independently pair these14types (decimal codes):

| Code | Meaning |
|---|---|
| 1 | Engine oil |
| 2 | Front brakes |
| 3 | Brake fluid |
| 4 | Micro-filter |
| 5 | Recirculating air filter |
| 6 | Rear brakes |
| 10 | Spark plugs |
| 11 | Air filter element |
| 12 | Fuel filter |
| 100 | Vehicle check |
| 20 | Pre-delivery inspection |
| 21 | Running-in check |
| 32 | Statutory vehicle inspection |
| 33 | Statutory emissions test |

`ui/service_history_page.py:AddServiceDialog.SERVICE_ITEMS` currently labels
code4asOilfilter as well as cabinfilter, and guesses coolant0x12/transmission0x23.
These mappings have no support in the two newly inspected catalogues. Correct
new-entry choices from evidence, preserve existing unknown codes, and don't map
an oil-filter selection to the cabin filter. This is queued for implementation;
this research change does not modify the UI or enable its live write worker.

## Ideas worth carrying into our app

| Priority | Idea | Adaptation to approved behavior |
|---|---|---|
| Current milestone | Accurate item choices and item/status detail | Use sourced IDs, one dated multi-item record, English labels, original unknown values retained |
| Current milestone | Compact record cards with expandable item detail | Date/mileage/garage/status visible together; keep initial page publication settled under D-23 |
| Current milestone | Remembered garage suggestions | Local QSettings preference, explicit independent/BMW flag,7ASCII-byte validation and no silent truncation |
| Current milestone | Readable write-plan preview and per-step journal | Show target, preserved/new entries and activation implications; raw frames stay in troubleshooting logs; existing no-Cancel/global write lockout remains |
| Current milestone | Interchange with existing files | Explicit .json/.tst/.bmwsh format adapters with strict validation and provenance; an imported list remains file evidence, not a fresh car baseline |
| Later optional | Offline multipart QR transfer | The repository's transfer.py uses versioned bytes, raw DEFLATE, Base45 and a CRC32 transfer ID; useful phone-to-desktop idea without a server, not required now |
| Later CBS scope | Service-due cards and before/after reset evidence | cbs.py contains concrete41xx/1001 decoding/reset leads for specified F-series ECUs; independently recover exact variants before adding CBS, which D-09 defers |

Do not adopt mileage sorting/drag ordering as an unproven car chronology rule;
D-37 allows backdated conflicting mileage. File ordering and headunit insertion
semantics still need evidence. Do not copy the source's default erase workflow,
missing-baseline assumption, loose positive response handling, partial live
publication or two-click write arming in place of our required confirmation.
The replay/map/3D features are unrelated to Task B and some use internet map
services; they are not proposed for this offline service milestone.

## License and next work

The repository declares PolyForm Noncommercial1.0.0 in LICENSE.md, rather than a
permissive license. No third-party code/assets were copied into the app. Reusing
code later must account for that license and notices; the independent protocol
facts above have original PRG/native corroboration where stated.

Next: correct the service catalogue in the implementation slice; independently
verify ADD-only preservation/capacity/order and activation/results on the exact
headunit; continue looking for a real read/storage path. Complete read/backup
and same-day checking remain unresolved. Screenshots/manual reconstruction are
not silently substituted for the approved complete baseline. Task B stays open.

## CBS priority update — D-58

The source observations above remain historical evidence; their CBS-later scope
label is superseded by the owner's2026-10-29priority change. CBS reading/writing
is required before easy and advanced coding. The exact pinned cbs.py source is
now the starting porting reference in [the promoted task](../../tasks/future-cbs-research.md).
This update does not turn upstream vehicle claims into this project's physical
observations or declare unresolved version fields verified.
