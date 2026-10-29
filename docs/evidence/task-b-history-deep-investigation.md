# History investigation and runtime boundary — 2026-10-29

**Primary implementation references; observed locally.** No vehicle request,
source executable execution, license alteration or physical validation occurred.
Retained inputs/reports/scripts and SHA-256 values are in
[the local evidence manifest](task-b-history-deep-manifest.json).

## Development and runtime

REA is a development tool for recovering behavior, algorithms, formats and data,
not only for writing specifications. Application code implements the recovered
contracts in Python. The runtime audit found no REA import, invocation or runtime
dependency in 32 app/UI/main modules, requirements or packaging inputs. Offscreen
source startup loaded no research tools. The new history module uses only the
Python standard library. Research binaries, scripts, docs and evidence remain
outside the shipped application. No runtime REA service, analysis engine, source
executable or source database generator is required.

## Is the Pro reader present behind a key?

Disabled features can contain their implementation in a binary. That general
possibility is valid; it does not establish the layout of this exact build.
SHM.exe SHA-256 is
`2d6bb52808f1754ac9334958530c5b2c60ec373fa35b674f28bdb34dc93cf92a`.
REA/Ghidra 12.1.4, PE resources/imports, Delphi forms and mapped native bytes were
examined alongside local objdump decoding. Ghidra did not define these Delphi
methods as functions, so no successful decompilation is claimed.

- Read-header case3 at `0x628e1d` unconditionally shows “Only in PRO version”;
  see [the retained first trace](task-b-recovered-contracts.md).
- Four parsed application forms contain no observed activation/key-entry edit
  control. Info `txtLicence` and `txtSerial` are TStaticText, with fixed Lite/free
  and placeholder serial captions. FormShow `0x627dc4` starts an image animation.
- Buy `0x627ce8` unconditionally opens the publisher's pricing URL through
  ShellExecuteW. The erase checkbox handler `0x60f0bc` forces erase back on and
  shows the same Pro message when unchecked. Neither handler checks a key.
- The PE inventory contains 57 resources. Its RCDATA are four application forms,
  platform marker and the UDP component data. No separate Pro module was
  identified in this inventory; this is not a proof against every hidden path.
- A full .text scan for direct E8 calls to the common ENET exchange `0x60d9d4`
  finds only `0x60ec67`, `0x60ed7d`, `0x60edbb`: erase, add, reset. Their argument
  literals are target `63`, `3101A080`, `3101A081`, `1101`. An E8 scan does not
  rule out indirect callers or a different network implementation.

REA byte observations include `ev_2aa8844f3db27e622641df7f5c07f1d5db3f4594e32fb61f7e61d18fd36c1076`
(Buy), `ev_84d2eecef2194deaaeec99028904436d92dc5d8ab45112791411a1df0e2fb38f`
(erase checkbox), and `ev_6291110a779478401d43569687450a1dc7ac50b2f892466ace90997b6a6c8d87`
(record display/date parsing). Exact additional native regions, form properties,
source hash and call coordinates are retained in the manifest's deep local report.

**Conclusion:** the assertion “a key only enables the existing reader” is not
confirmed for the supplied Lite build. The search extends beyond the UI stub,
but no complete headunit maintenance-history reader has been recovered. This is
a bounded negative result, not a universal assertion that no such code exists.
A separate Pro build is one possible evidence source, not an established
architectural requirement. Continue source investigation without changing locks
or guessing read requests from destructive routine identifiers.

## Recovered local record and add payload

All four primary headunit PRGs (CIC, NBT, NBTEVO, HU_MGU) independently encode
`STEUERN_SERVICEHISTORY_ADD` as `31 01 A0 81` followed by the record below.
The NBT job starts at BEST offset `0x13763b`; the retained four-job report
contains all job comments, disassembly and result tables. Each declares 61
arguments: nine header arguments plus four for each of thirteen items.

| Record offset | Bytes | Meaning |
|---|---|---|
| 0, 1 | 1 each | Day, month |
| 2 | 2 | Year, unsigned big-endian |
| 4 | 1 | Correction counter |
| 5 | 4 | Mileage km, unsigned big-endian |
| 9 | 1 | Dealer flag |
| 10 | 7 | ASCII dealer field, right NUL padding for shorter names |
| 17 | 1 | Overall status |
| 18 | 1 | Item count |
| 19 onward | 8 each | Code1, status1, signed BE32 remaining distance, unsigned BE16 remaining time |

Native record display at `0x628b39` copies exactly seven dealer bytes; status
loads at `0x628b66` use offset17, and count at `0x628c06` uses offset18. The
supplied 360-byte .bmwsh file parses into eight records of lengths
67,35,27,51,51,59,43,27, and round-trips byte-for-byte with the fixed format.
The earlier variable-NUL-terminated dealer hypothesis is **disproven**: NUL is
padding inside a seven-byte field, not a variable record boundary. The file and
recovered add body agree for these artifacts; that does not make an imported
file a current vehicle baseline or establish complete vehicle read semantics.

`app/service_history.py` now provides immutable decoded records, exact original
byte preservation, local serialization, a separately explicit NBT add-payload
encoder and final business-result decoder. Unknown existing codes/statuses,
padding, dealer bytes, zero or >13 item counts survive local round-trip.
The 1 MiB local-file ceiling is a resource policy, not an ECU capacity claim.
New add requests reject future/same-day entries, invalid integer ranges/statuses,
non-ASCII/overlength dealer input and item counts outside1..13. Input is never
silently truncated. Backdated dates and entered mileage remain allowed.

The supported positive ADD reply shape is `71 01 A0 81 result`, with the
source extracting result at PDU offset4. Shared
SERVICEHISTORY tables:00 Everything OK,01 out of memory,02 data inconsistency,
04 no writing permission,05 unknown error. Unknown results never mean accepted;
MGU also labels FF invalid. The decoder checks the echo and requires exactly five bytes. Replies with
additional bytes fail closed pending their recovery; the source extraction
does not prove that every variant always returns exactly five bytes.
`accepted` means application acceptance, not observed history verification.
No send worker is enabled by this module.

## Expanded read search and remaining execution gaps

The four primary headunits plus BIS01, CHAMP2, ENAVEVO, ENTRY, ENTRYNAV, RAD_UKL
provide ADD/ERASE but no recovered headunit-list read in their parsed jobs.
They have no imported USES jobs. Broad search covered 2,482 PRG/GRP files;
format-aware review distinguishes unrelated uses of “history”. Generic
STATUS_LESEN is selector constrained; D01E is software-update installation
history. MOST registries are unrelated to the service list.

A real CBS6.3 history read `22 10 04` exists in KOMBSP21/D94BX7A0/DME9FF_R,
with reset type, CBS IDs and before/after values. It contains neither proof of
the complete NBT headunit list nor garage/multi-item record recovery. Likewise,
oil-history aggregate404F is not that archive. A scan of 861 decrypted diagnostic
JSON assets found no additional maintenance/CBS history sensor entry.

Remaining: complete headunit history read/framing/capacity/unknown-data contract,
identity/session prerequisites, preserving append semantics, activation/cycle
requirements and physical validation. Native reset1101 after writes is a lead,
not a universal reset permission or validated ignition-cycle policy. The
application's existing history mutation guards remain active until these
requirements are met. Coding/MIL/DoIP gaps remain separately tracked in spec26;
Task B is not complete.
