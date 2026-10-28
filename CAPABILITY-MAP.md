# Capability map — goals and current evidence

Updated 2026-10-28. Single desktop app, one active vehicle connection. This is
not a completed-feature certificate. See [the audit](docs/19-audit-and-readiness.md).

| Capability | Intended behavior | Current evidence / blocker |
|------------|-------------------|----------------------------|
| Connection | ENET discovery, transport selection, correlated identity | Partial historical F48 traffic; PR #8 pending review; no confirmed end-to-end success |
| Vehicle information | Identity, versioned ECU inventory, available mileage/voltage/FA | UI and read paths exist; key DIDs/codecs are unverified |
| Diagnostics | Per-ECU DTC read/clear, descriptions and emissions MIL | Code/demo exist; format, incomplete-scan and MIL semantics need review |
| Service history | Read/write headunit-local records | Conflicting protocol claims; current “read” uses a candidate add routine |
| Easy coding | Compatible presets with live current values | Database parsing/UI exist; exact variant matching and complete baseline/encoder missing |
| Advanced coding | Versioned ECU parameters with validated hex editing | Definition browsing exists; vehicle write/readback not established |
| Backups/recovery | Backup before coding/history writes, retain intended state, confirm by readback | Owner requirement; current UI-value manifests do not provide verified vehicle rollback |
| Demo | Explore UI with a canned F48 fixture | Useful UI simulation; no transport or hardware validation |
| Distribution | Offline macOS and Windows desktop binaries | Build examples exist; clean installs/platform release builds unverified |

Build/review order: connection → read-only identity/inventory → diagnostics and
history/coding reads → backup/readback/recovery → verified mutations → broader
variant coverage → platform release validation. Research can inform wider
coverage; physical validation is currently limited to the owner's F48/NBT.
