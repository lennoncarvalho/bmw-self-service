# DTC Description Database

> Ship `dtc_descriptions.db` as a read-only app asset. Load once at startup.
> 88,580 entries. English + German. 18.9 MB.

---

## Quick reference

| | |
|---|---|
| **File** | `dtc_descriptions.db` |
| **Size** | 18.9 MB |
| **Entries** | 88,580 |
| **Languages** | German (`text_de`) + English (`text_en`) — all user-facing entries translated |
| **Lookup** | O(1) indexed, read-only SQLite |
| **Tables covered** | FORTTEXTE (55K), IORTTEXTE (16K), FARTTEXTE (33) |

## Schema

```sql
CREATE TABLE dtc_descriptions (
    code        TEXT NOT NULL,     -- uppercase hex, e.g. "B7F805"
    text_de     TEXT NOT NULL,     -- original German description
    text_en     TEXT,              -- English translation
    ecu         TEXT,              -- source ECU name (e.g. "BDC", "NBT")
    table_type  TEXT,              -- "FORTTEXTE" | "FARTTEXTE" | "IORTTEXTE" | ...
    translated  INTEGER DEFAULT 0, -- always 1 for user-facing entries
    PRIMARY KEY (code, table_type)
);
CREATE INDEX idx_code ON dtc_descriptions(code);
```

## DtcDatabase class

Ship this class with the app. Load the database once, reuse the connection.

```python
import sqlite3

class DtcDatabase:
    """Read-only, thread-safe DTC lookup. O(1) indexed per code."""

    def __init__(self, db_path="assets/dtc_descriptions.db"):
        self.conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)

    def describe(self, code: str) -> str | None:
        """Look up a DTC code. Returns English text, falls back to German.

        >>> dtc_db.describe("B7F805")
        'Connection head unit to DAB L-band antenna base: line disconnection'
        """
        code = code.upper().replace("0X", "").replace("0x", "")

        row = self.conn.execute(
            "SELECT text_en, text_de FROM dtc_descriptions WHERE code = ? LIMIT 1",
            (code,)
        ).fetchone()

        if row:
            return row[0] or row[1]

        return _OBD2_CODES.get(code)

    def describe_with_ecu(self, code: str) -> tuple[str, str] | None:
        """Return (description, ecu_name) or None.

        >>> dtc_db.describe_with_ecu("8040BD")
        ('Terminal 30F reset or shutdown', 'BDC')
        """
        code = code.upper().replace("0X", "").replace("0x", "")

        row = self.conn.execute(
            "SELECT text_en, text_de, ecu FROM dtc_descriptions WHERE code = ? LIMIT 1",
            (code,)
        ).fetchone()

        if row:
            return (row[0] or row[1], row[2])
        return None

    def fault_type(self, type_code: str) -> str | None:
        """Describe a fault type byte from DTC status mask.

        >>> dtc_db.fault_type("08")
        'implausible signal or value'
        """
        row = self.conn.execute(
            "SELECT text_en, text_de FROM dtc_descriptions "
            "WHERE code = ? AND table_type = 'FARTTEXTE' LIMIT 1",
            (type_code.upper(),)
        ).fetchone()
        return (row[0] or row[1]) if row else None


# Singleton — load once at app startup
dtc_db = DtcDatabase()
```

## Usage: read DTCs from a car

```python
def read_dtcs(conn, ecu_addr: int) -> list[dict]:
    """Read DTCs from an ECU and return rich descriptions.

    Returns list of dicts with: code, status_byte, description

    UDS flow:
      10 03        → DiagnosticSessionControl (extended session)
      19 02 08     → ReadDTCInformation (by status mask, confirmed DTCs)
    """
    dtcs = []

    # Extended diagnostic session
    conn.send_uds(ecu_addr, bytes([0x10, 0x03]))

    # Read confirmed DTCs
    resp = conn.send_uds(ecu_addr, bytes([0x19, 0x02, 0x08]))
    if resp[0] != 0x59:        # negative response — no DTCs or ECU doesn't support
        return dtcs

    # Parse response: 0x59 + status_mask_echo + [3-byte DTC + 1-byte status]*
    offset = 2
    while offset + 4 <= len(resp):
        code = resp[offset:offset+3].hex().upper()
        status = resp[offset+3]
        desc = dtc_db.describe(code) or "(no description)"

        dtcs.append({
            "code": code,
            "status_byte": status,
            "description": desc,
        })
        offset += 4

    return dtcs


# Example: read DTCs from headunit (ECU 0x63)
for dtc in read_dtcs(hsfz, 0x63):
    print(f"{dtc['code']}: {dtc['description']}")
    # B7F805: Connection head unit to DAB L-band antenna base: line disconnection
    # B7F807: Connection head unit to DAB L-band antenna base: short circuit
    # 026300: Energy saving mode active
```

## Usage: clear DTCs

```python
def clear_dtcs(conn, ecu_addr: int):
    """Clear all DTCs from an ECU.

    UDS: 14 FF FF FF → ClearDiagnosticInformation (all DTCs)
    """
    conn.send_uds(ecu_addr, bytes([0x14, 0xFF, 0xFF, 0xFF]))
```

## UDS 0x19 sub-function reference

Per ISO 14229-1. BMW follows the standard for these sub-functions.

| Sub-function | ISO name | Common usage |
|-------------|----------|-------------|
| `0x19 01` | reportNumberOfDTCByStatusMask | Quick check: any faults? |
| `0x19 02` | reportDTCByStatusMask | Read all confirmed/pending DTC codes |
| `0x19 03` | reportDTCSnapshotIdentification | Which DTCs have freeze-frame data? |
| `0x19 04` | reportDTCSnapshotRecordByDTCNumber | Read freeze-frame for one DTC (needs DTC+record params) |
| `0x19 06` | reportDTCExtDataRecordByDTCNumber | Read extended data (environment, aging counters) |

### Snapshot identification (0x19 03)

Request: `0x19 03` (no parameters)
Response: `0x59 03 + [DTC(3) + status(1) + snapshot_count(1) + records...]*`

Each record (when snapshot_count > 0), BMW-specific format (tentative):
`record_num(1) + timestamp(4) + mileage(4)`

- **timestamp**: Seconds since 2000-01-01 00:00:00 UTC (BMW convention, needs per-chassis verification)
- **mileage**: Kilometers × 10, big-endian uint32 (BMW convention, needs per-chassis verification)

Example: `0x59 03 B7F805 08 01 01 A1B2C3D4 0001A340`
→ DTC B7F805, 1 snapshot, record #1, timestamp=..., mileage=10,732.8 km

### Snapshot record (0x19 04)

Request: `0x19 04 [DTC(3)] [record_num(1)]`
Response: `0x59 04 [DTC(3)] [status(1)] [record_num(1)] [snapshot_data...]`

Snapshot data format is ECU-specific. Common DID→value pairs:
- Engine RPM, vehicle speed, coolant temperature, battery voltage
- Ambient temperature, intake air temperature
- Fuel system status, calculated load

The snapshot data format varies by ECU and is not decoded by this app.
Only the timestamp and mileage from 0x19 03 are used for display.

## DTC code format

BMW hex codes from UDS `0x19` responses:

```
B7F805
│││└── Fault code (0x05)
││└─── Sub-category
│└──── ECU identifier (0xF8 = headunit)
└───── Platform prefix (0xB7 = F/G-series)
```

The car returns 3-byte codes. Normalize by uppercasing and stripping `0x` prefix before lookup.

## OBD-II P-code fallback

Standard P-codes (P0xxx-P3xxx) per SAE J2012. Extend as needed:

```python
_OBD2_CODES = {
    "P0100": "Mass or Volume Air Flow Circuit Malfunction",
    "P0101": "Mass or Volume Air Flow Circuit Range/Performance",
    "P0171": "System Too Lean (Bank 1)",
    "P0172": "System Too Rich (Bank 1)",
    "P0300": "Random/Multiple Cylinder Misfire Detected",
    "P0420": "Catalyst System Efficiency Below Threshold (Bank 1)",
    # ... complete from SAE J2012 / ISO 15031-6
}
```

## Why SQLite

| Factor | SQLite | JSON |
|--------|--------|------|
| Lookup | O(1) indexed | O(n) scan, or full load into RAM |
| Memory | Queries on disk | Must load entire file |
| Startup | Instant | Must parse entire file |
| Thread safety | `mode=ro`, concurrent reads | Needs locking |
| Size | 18.9 MB | ~25 MB equivalent |

---

## Appendix: provenance

The database was built once from BMW PRG files and translated once via a local
LLM. It is a static asset — never rebuilt during app development.

| Step | Tool | Input | Output |
|------|------|-------|--------|
| Extract | `extract_dtc.py` | 2,571 PRG files | 88,580 entries (German) |
| Translate | `translate_ollama.py` | German SQLite | 71,439 entries (English) |

Both scripts are kept for reference in the repo root. See their `--help` for
usage. The extraction requires `BimmerDaten/decoderPrg.py`. Translation requires
Ollama with `qwen2.5:3b`.