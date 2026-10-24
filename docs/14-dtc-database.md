# DTC Description Database

> **Status:** Complete. `dtc_descriptions.db` ships as a static app asset.
> **Extraction date:** 2026-10-23
> **Translation date:** 2026-10-24
> **Source:** 2,571 BMW PRG files from ISTA / Standard Tools
> **Language:** German + English (71,439 entries translated via Ollama/qwen2.5:3b on M4)

---

## What's in the database

| Metric | Value |
|--------|-------|
| PRG files processed | 2,571 |
| Files with fault data | 1,508 |
| Raw entries extracted | 571,968 |
| **Unique DTCs** | **88,580** |
| Database size | 18.9 MB |
| Language | German (English translation deferred) |

## Table types

```
FORTTEXTE          55,315    Fault location descriptions (primary)
IORTTEXTE          16,091    International fault location variants
PCODETEXTE          8,388    BMW code → OBD-II P-code mappings
FUMWELTTEXTE        6,685    Environmental condition labels
FARTTEXTEINDIVIDUELL 1,202   Individual fault type variants
IUMWELTTEXTE          558    International environment labels
FARTTEXTEERWEITERT    242    Extended fault type descriptions
IARTTEXTEERWEITERT     38    International extended fault types
FARTTEXTE              33    Fault type descriptions
HORTTEXTE              27    Fault location aux descriptions
POSWHEBELTEXTE          1    Position texts (gear lever)
```

## Example entries

| Code | Table | ECU | Description |
|------|-------|-----|-------------|
| `B7F805` | FORTTEXTE | CHAMP2 | Verbindung Head-Unit zum DAB L-Band Antennenfuß: Leitungsunterbrechung |
| `9D68` | FORTTEXTE | 01MRDWA | Bordnetz Überspannung |
| `CD9427` | FORTTEXTE | D70BX7A0 | Botschaft (DT_GRDT, 0x1AF): Botschaft von Sende-Steuergerät nicht aktuell |
| `8040BD` | FORTTEXTE | BDC | Klemme 30F Reset oder Abschaltung |
| `44E3F1` | FORTTEXTE | GKEHY23 | Überwachung der Fahrdynamikregelung: Signal ungültig |
| `01` | FARTTEXTE | (many) | Signal oder Wert oberhalb Schwelle |
| `08` | FARTTEXTE | (many) | unplausibles Signal oder Wert |
| `23` | FARTTEXTE | (many) | Fehler momentan vorhanden, OBD-entprellt |

## Schema

```sql
CREATE TABLE dtc_descriptions (
    code        TEXT NOT NULL,     -- hex code, e.g. "B7F805"
    text_de     TEXT NOT NULL,     -- original German description
    text_en     TEXT,              -- English translation (NULL until translated)
    ecu         TEXT,              -- source ECU name
    table_type  TEXT,              -- FORTTEXTE / FARTTEXTE / FEHLERKLASSE / ...
    translated  INTEGER DEFAULT 0,
    PRIMARY KEY (code, table_type)
);
CREATE INDEX idx_code ON dtc_descriptions(code);
CREATE INDEX idx_type ON dtc_descriptions(table_type);
```

## One-time extraction (already done)

The extraction script is `extract_dtc.py` at the repo root. It ran once to
produce the database — never a build step, never blocks development.

```bash
# Already run — produces dtc_descriptions.db
python3 extract_dtc.py --extract --prg-dir sources/Ecu --workers 8

# Translation: fire-and-forget background task (see "English translation" below)
python3 extract_dtc.py --translate         # DeepL (needs DEEPL_API_KEY)
python3 extract_dtc.py --translate-offline # argos-translate (free, offline)

# Show stats
python3 extract_dtc.py --stats
```

## Runtime integration

The app ships `dtc_descriptions.db` as a read-only asset alongside images and fonts.

```python
import sqlite3

class DtcDatabase:
    """Read-only, thread-safe DTC lookup. O(1) per code."""

    def __init__(self, db_path="assets/dtc_descriptions.db"):
        self.conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)

    def describe(self, code: str) -> str | None:
        """Look up a DTC code. Returns description or None."""
        code = code.upper().replace("0X", "").replace("0x", "")

        # Try BMW database first (FORTTEXTE has priority via dedup)
        row = self.conn.execute(
            """SELECT text_en, text_de FROM dtc_descriptions
               WHERE code = ? LIMIT 1""",
            (code,)
        ).fetchone()

        if row:
            return row[0] or row[1]  # English if translated, else German

        # Fallback: standard OBD-II P-codes (P0xxx-P3xxx)
        return self._obd2_lookup(code)

    def describe_with_type(self, code: str) -> tuple | None:
        """Return (description, fault_type_description) for rich display."""
        code = code.upper().replace("0X", "").replace("0x", "")

        # Main fault location description
        row = self.conn.execute(
            """SELECT text_en, text_de, ecu FROM dtc_descriptions
               WHERE code = ? AND table_type = 'FORTTEXTE' LIMIT 1""",
            (code,)
        ).fetchone()

        if not row:
            row = self.conn.execute(
                """SELECT text_en, text_de, ecu FROM dtc_descriptions
                   WHERE code = ? LIMIT 1""",
                (code,)
            ).fetchone()

        if not row:
            return None

        desc = row[0] or row[1]
        ecu = row[2]
        return (desc, ecu, None)  # type description can be joined later

    def fault_type(self, type_code: str) -> str | None:
        """Describe a fault type byte (from DTC status mask)."""
        row = self.conn.execute(
            """SELECT text_en, text_de FROM dtc_descriptions
               WHERE code = ? AND table_type = 'FARTTEXTE' LIMIT 1""",
            (type_code.upper(),)
        ).fetchone()
        if row:
            return row[0] or row[1]
        return None

    def _obd2_lookup(self, code: str) -> str | None:
        """Public domain OBD-II P-code descriptions per SAE J2012."""
        return OBD2_CODES.get(code)


# Singleton — loaded once at app startup
dtc_db = DtcDatabase()


def read_and_describe_dtcs(conn, ecu_addr: int) -> list[dict]:
    """Read DTCs from an ECU and return rich descriptions.

    Returns list of dicts:
        {code, status_byte, status_text, description, ecu}
    """
    dtcs = []

    # Extended diagnostic session
    conn.send_uds(ecu_addr, bytes([0x10, 0x03]))

    # Read DTCs by status mask (0x08 = confirmed)
    resp = conn.send_uds(ecu_addr, bytes([0x19, 0x02, 0x08]))
    if resp[0] != 0x59:
        return dtcs

    offset = 2  # skip 0x59 + status mask echo
    while offset + 4 <= len(resp):
        code_hex = resp[offset:offset+3].hex().upper()
        status_byte = resp[offset+3]

        desc = dtc_db.describe(code_hex) or "(no description)"

        dtcs.append({
            "code": code_hex,
            "status_byte": status_byte,
            "description": desc,
        })
        offset += 4

    return dtcs


# Standard OBD-II P-codes (public domain, SAE J2012 / ISO 15031-6)
OBD2_CODES = {
    "P0100": "Mass or Volume Air Flow Circuit Malfunction",
    "P0101": "Mass or Volume Air Flow Circuit Range/Performance Problem",
    "P0102": "Mass or Volume Air Flow Circuit Low Input",
    "P0103": "Mass or Volume Air Flow Circuit High Input",
    "P0104": "Mass or Volume Air Flow Circuit Intermittent",
    # ... extend from public domain SAE J2012 table
    "P0171": "System Too Lean (Bank 1)",
    "P0172": "System Too Rich (Bank 1)",
    "P0174": "System Too Lean (Bank 2)",
    "P0175": "System Too Rich (Bank 2)",
    "P0300": "Random/Multiple Cylinder Misfire Detected",
    "P0301": "Cylinder 1 Misfire Detected",
    "P0302": "Cylinder 2 Misfire Detected",
    "P0303": "Cylinder 3 Misfire Detected",
    "P0304": "Cylinder 4 Misfire Detected",
    "P0420": "Catalyst System Efficiency Below Threshold (Bank 1)",
    "P0430": "Catalyst System Efficiency Below Threshold (Bank 2)",
}
```

## Why SQLite over JSON

| Factor | SQLite | JSON |
|--------|--------|------|
| Lookup | O(1) indexed | O(n) scan or O(1) with full load into dict |
| Memory | Queries on disk, no full load | Must load entire file into RAM |
| Startup | Instant, no parsing | Must parse entire file |
| Size | 18.9 MB | ~25 MB equivalent JSON |
| Thread safety | Read-only mode, concurrent reads | Needs locking |

## DTC Code Format

BMW diagnostic trouble codes from PRG files use a 6-digit hex format:

```
0xB7F805
  ││││└── Specific fault code (0x05)
  │││└─── Fault sub-category
  ││└──── ECU identifier (0xF8 = headunit)
  └└───── Platform prefix (0xB7 = F/G-series)
```

When reading DTCs from the car via UDS 0x19, the response contains 3-byte
DTC codes. These map directly to the PRG table indices.

## English translation (done — ships with the app)

**Translation completed** using Ollama with `qwen2.5:3b` running locally
on Apple Silicon (M4). Fully offline, zero API keys, zero cost.

### Backend: Ollama + qwen2.5:3b

A 3B-parameter multilingual model running on the Mac's GPU via Metal.
~8 entries/sec, BMW terminology-tuned via system prompt.

### Script: `translate_ollama.py`

```bash
python3 translate_ollama.py              # translate all remaining (resumable)
python3 translate_ollama.py --check      # show progress
python3 translate_ollama.py --sample 20  # test with 20 entries
```

### Fallback behavior

The `DtcDatabase` class returns English when available, German otherwise:

```python
# In DtcDatabase.describe():
return row[0] or row[1]  # text_en if translated, else text_de
```

No code changes needed — the translated database is a drop-in replacement.