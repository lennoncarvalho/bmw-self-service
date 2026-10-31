# Coding presets learned by diff (D-66)

Status: Phase 1 (read-only capture, diff, preset store, UI) implemented and
verified offline. Phase 2 (applying a preset) is pending. No vehicle traffic has
been exchanged with this feature yet.

## Workflow

1. Coding page → "Learn coding option" → choose an exactly identified UDS ECU
   from the connected car's inventory.
2. **Capture before.** The app reads the ECU's coding identity and its coding
   data identifiers and saves the capture to disk.
3. The owner disconnects this app, applies exactly ONE option with their own
   coding app, closes it and reconnects this app (only one tool may use the car
   at a time). The before-capture survives on disk, keyed by VIN, ECU address,
   variant and F101.
4. **Capture after.** The panel diffs the latest complete before/after pair of
   that ECU and shows each change as DID / byte offset / mask / old → new bits.
5. The owner enters a label (and optional notes) and saves the preset. The list
   shows the car's presets with applicability: "applicable to this ECU" when the
   preset's F101 equals the ECU's latest capture, "learned on another coding
   version" otherwise.

Presets are the owner's own data, learned from the owner's captures.

## Capture contract (`app/coding_learn.py`, `CodingCaptureWorker`)

- `22 F101`; decoded with `app.coding.decode_cafd_identifiers`; at least one
  CAFD identifier is required, otherwise the capture fails before scanning.
- `22 DID` for every DID 0x3000–0x3FFF. D-65 relaxed read: NRC 0x31 = DID absent
  (counted); other negative codes are recorded per DID. Positive replies must echo
  the DID.
- One overall budget of 240 s including queueing; each request's context is
  `min(30 s, remaining)` and no request is sent with < 1 s left (a reply cut off
  by the deadline would quarantine the ECU). Progress every 64 DIDs.
- Stop is honoured between DIDs; in-flight reads use an uncancelled token
  because cancelling one would end the connection.
- Timeout, lost connection, invalid echo, budget exhaustion, interruption, no
  coding DID answering, or F101 changing on the final reread → capture is saved
  with `complete: false` and a reason; incomplete captures never form a preset.
- Only `22` requests are sent, so it works in `--read-only` sessions. HSFZ only
  (ECU addresses come from the HSFZ inventory).
- Lockout: `CodingPage.is_reading()` includes the capture, so
  `MainWindow._can_start_mutation` blocks CBS reset, DTC clear and history writes
  while it runs; a capture starts only when `_can_start_mutation()` is true and
  the page's coding snapshot read is not running. Disconnect retires the worker.

## Files and formats

- Captures: `~/BMW-Tool/coding/captures/<VIN>-<addr>-<UTC>-<role>-<id8>.json`,
  `schema_version 1`, `kind coding-capture`: role, VIN, ECU
  {name, address, variant, address_index}, F101 raw hex, CAFD ids, range,
  `blocks {DID: hex}`, `negative {DID: NRC}`, absent count, scanned count,
  complete/reason, timestamps, duration, content sha256. Atomic temp-file
  replace with file and directory fsync; never rewritten.
- Presets: `~/BMW-Tool/coding/presets.json`, `schema_version 1`,
  `kind coding-presets`, `presets {id: preset}`, whole-file sha256, ≤ 4 MiB,
  ≤ 500 presets. Preset: label, notes, `source learned-by-diff`, created, VIN,
  ECU {name, address, variant}, CAFD ids, F101 raw (exact applicability),
  changes `[{did, offset, mask, old, new}]` (old/new are masked values), and the
  before/after capture paths with file sha256. A damaged database is reported
  and left unmodified; a second preset from the same after-capture is refused.
- `diff_captures` requires both captures complete, same VIN, ECU address and
  variant, identical F101 raw, identical DID sets and block lengths.
- UI: `ui/coding_learn_panel.py` (embedded in `ui/coding_page.py`), wiring in
  `ui/main_window.py`.

## Verification (2026-10-30, offline)

One-off script in the session scratchpad (not in the repo) with the real
`HSFZConnection` and a fake HSFZ gateway answering `7F 22 31` for unknown DIDs,
scripted with the owner log's HKFM (0x0D) F101 and its 19 blocks 3000–3122
(`session-20261029T212526.928470Z-1322-filtered.log`):

- Read-only session: complete capture, 19 blocks, CAFD `000007C8-007-001-017`,
  4098 requests all `22`, 1.4 s for the 4096-DID scan on localhost.
- One flipped bit → exactly one change (DID 3030 byte 0, mask 0x04, 0x04 → 0x00).
- Refused: F101 changed between captures; F101 changed during capture
  (incomplete); DID present in only one capture; duplicate preset; tampered
  capture file; tampered preset database.
- Interruption, budget exhaustion and a silent DID (timeout) → incomplete,
  persisted, connection still alive after Stop; unidentified ECU → refused with
  no traffic.
- Qt offscreen: CodingPage capture before/after through the panel, lockout
  refusal while `can_capture()` is false, diff shown, preset saved and listed
  with applicability, flow restored from disk by a fresh panel, no Apply button.
- Mutation probes: removing the F101 comparison, the F101 reread, the mask on
  `old`, or the DID-set check each made the script fail.
- `scripts/preflight.sh` green.

## Limits

- Real ECU scan time is unmeasured; expect tens of seconds to a few minutes per
  capture depending on the ECU's negative-reply latency.
- Coding data outside 0x3000–0x3FFF is not captured.
- A diff of more than one byte is shown with a warning; the app cannot tell
  whether the owner applied one option or several.

## Phase 2 (pending): apply a preset

Strict D-65 write contract: reread F101 and require an exact match with the
preset; complete backup capture of the ECU before writing; owner confirmation
and power acknowledgement; durable journal; lockout; write each affected DID as
current block with only the masked bits replaced (`2E`), checked completion,
readback, restore path from the backup, no replay of uncertain outcomes.
