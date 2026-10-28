# Capability map — goals and current evidence

Updated 2026-10-28. Single desktop app, one active vehicle connection. This is
not a completed-feature certificate. See [the audit](docs/19-audit-and-readiness.md).
Current work: [Task A](tasks/protocol-library-migration.md) and
[Task B](tasks/rea-protocol-recovery.md); acceptance in
[spec 26](docs/26-feature-readiness-spec.md), source answers in
[doc 27](docs/27-rea-source-guide.md).

| Capability | Intended behavior | Current evidence / blocker |
|------------|-------------------|----------------------------|
| Connection | ENET discovery, transport selection, correlated identity | Two retained HSFZ/session/VIN successes on owner F48; optional data and real ECU inventory still missing |
| Vehicle information | Identity, versioned ECU inventory, available mileage/voltage/FA | UI and read paths exist; key DIDs/codecs are unverified |
| Diagnostics | All-ECU fault display, one Clear All and supported MIL status | Four positive empty gateway-only reads, explicitly incomplete; full ECU coverage, clearing and MIL not validated |
| Service history | Read/add headunit history first; edit/delete/replace later | Live read/write unavailable; former add-like automatic request disabled; encoder/readback still required |
| Easy coding | Compatible presets with live current values | Database parsing/UI exist; exact variant matching and complete baseline/encoder missing |
| Advanced coding | Later priority after all applicable easy presets | Vehicle write/readback not established; not required for initial usable slice |
| Backups/recovery | Backup before coding/history writes, retain intended state, confirm by readback | Owner requirement; current UI-value manifests do not provide verified vehicle rollback |
| Demo | Explore UI with a canned F48 fixture | Useful UI simulation; no transport or hardware validation |
| Distribution | Offline macOS and Windows desktop binaries | Build examples exist; clean installs/platform release builds unverified |

Build/review order: connection → read-only identity/inventory → diagnostics and
history/coding reads → backup/readback/recovery → verified mutations → broader
variant coverage → platform release validation. Research can inform wider
coverage; physical validation is currently limited to the owner's F48/NBT.
