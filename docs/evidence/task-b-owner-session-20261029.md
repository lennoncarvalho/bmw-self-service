# Owner F48/NBT read-only session — 2026-10-29T21:25Z

Status: **observed locally** on the owner's car only. Not fleet validation.
The owner supplied the filtered session log on 2026-10-30; it stays local because
it contains VIN, MAC and host details (as with [doc 23](../23-first-vehicle-session.md)).

- Log: `~/BMW-Tool/logs/session-20261029T212526.928470Z-1322-filtered.log`,
  SHA-256 `e38c106ce58baffc5819b464a8176a3dd9843794e1f628b6856990bdd0637f25`.
- App revision `85ed2ad` (main after PR16), `--read-only`, debug logging; Python
  3.15.2 (not the 3.13 target), PySide6/Qt 6.12.0, macOS 26.6.2 arm64, USB
  Ethernet `en15`, HSFZ discovery and VIN as in doc 23.

## Identity and topology

Gateway `22 3F07` announced 19 ECUs; every `22 F150` matched an exact catalogue row:

| Addr | Variant | Name | Addr | Variant | Name |
|---|---|---|---|---|---|
| 01 | 0F16EA | ACSM4I | 43 | 0F1E20 | FLE_L |
| 06 | 0F1D00 | ICAM_F15 | 44 | 0F1E30 | FLE_R |
| 0D | 0F1738 | HKFM11 | 56 | 0F1CF0 | FZD_F15 |
| 10 | 0F1310 | ZGW_01 | 60 | 0F1630 | KOMB25 |
| 12 | 0F1D22 | DME_BX8 | 61 | 0F1A50 | TCB1 |
| 18 | 0F1C80 | GSAW01 | 63 | 0F1BE0 | ENTRYNAV |
| 29 | 0F1970 | DSC_I1 | 67 | 0F2290 | ZBE6 |
| 2C | 0F1B60 | PMA_15 | 6D | 0F1960 | FAS_12 |
| 30 | 0F1980 | EPS_I1 | 78 | 0F1C70 | IHX_I1 |
| 40 | 0F19C0 | BDC | | | |

## Findings and dispositions

1. **First connection lost after one slow ECU.** About 0.1 s after connecting,
   `22 F150` to ACSM `0x01` received the HSFZ ACK but no reply within the 5 s
   P2 timer. The owner closed the stream, so vehicle order, I-level and voltage
   all failed. On the reconnect 23 s later, `0x01` answered in under 1 ms.
   **Fixed (commit 152df53):** a timed-out pure read on intact HSFZ framing
   blocks only that ECU until its late final reply is consumed by source address
   (spec 25 invariant 2). Mutations, partial frames and DoIP still reconnect.
2. **I-level rejected.** `22 100B` returned 39 data bytes: three blocks
   `F056 11 03 01F9` (F056-17-03-505) followed by 15 more bytes. The decoder
   required exactly 24. The coding source requires at least three blocks and
   ignores the rest (`FSeriesVehicleInterface` `s0$c.b`: length ≥ 0x1B, slices
   3–11/11–19/19–27; BimmerCode APK SHA-256 `fc6eedeb…b728`). **Fixed.** The
   meaning of the trailer is unresolved; it is not displayed.
3. **MIL reported ON.** DME_BX8 `22 4A69` → `62 4A69 01` (B_mil, "condition
   MIL lamp on"), while DME `19 02 0C` returned no pending/confirmed records and
   `22 402B` decoded ≈12.0 V. **Owner confirmed 2026-10-30: engine off,
   ignition/key on** during this session. `B_mil = 1` is therefore consistent
   with the key-on bulb check, not with a stored emissions fault. Under owner
   decision D-59 the indicator now follows engine fault memory instead: this
   session's DME `59 02 FF` (no records) shows OFF.
4. Supply voltage: `402B` 31-byte layout decoded on both reads (≈12.0 V).
5. `19 15` is rejected with `7F 19 12` on 17 of 19 ECUs; DME and DSC answer
   `59 15 FF` with no records. `0x40` and `0x29` used `7F xx 78` before final
   replies. Existing handling was correct.
6. Coding snapshots: exact reported coding definitions were missing locally for
   12 ECUs (incl. `0x01`, `0x12`, `0x60`, `0x63`). This belongs to easy-coding
   scope (queue 7) and was not changed here.

No odometer, CBS or history request was sent in this session. No mutation.
