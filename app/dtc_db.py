"""DTC (Diagnostic Trouble Code) description database.

Read-only SQLite descriptions. 88,580 rows with indexed code lookup.
English preferred, German fallback.

Reference: docs/14-dtc-database.md
"""

import logging
import sqlite3

# Standard OBD-II P-code fallback (SAE J2012 / ISO 15031-6)
_OBD2_CODES: dict[str, str] = {
    "P0100": "Mass or Volume Air Flow Circuit Malfunction",
    "P0101": "Mass or Volume Air Flow Circuit Range/Performance",
    "P0102": "Mass or Volume Air Flow Circuit Low Input",
    "P0103": "Mass or Volume Air Flow Circuit High Input",
    "P0105": "Manifold Absolute Pressure/Barometric Pressure Circuit Malfunction",
    "P0106": "Manifold Absolute Pressure/Barometric Pressure Circuit Range/Performance",
    "P0107": "Manifold Absolute Pressure/Barometric Pressure Circuit Low Input",
    "P0108": "Manifold Absolute Pressure/Barometric Pressure Circuit High Input",
    "P0110": "Intake Air Temperature Circuit Malfunction",
    "P0111": "Intake Air Temperature Circuit Range/Performance",
    "P0112": "Intake Air Temperature Circuit Low Input",
    "P0113": "Intake Air Temperature Circuit High Input",
    "P0115": "Engine Coolant Temperature Circuit Malfunction",
    "P0116": "Engine Coolant Temperature Circuit Range/Performance",
    "P0117": "Engine Coolant Temperature Circuit Low Input",
    "P0118": "Engine Coolant Temperature Circuit High Input",
    "P0120": "Throttle/Pedal Position Sensor A Circuit Malfunction",
    "P0121": "Throttle/Pedal Position Sensor A Circuit Range/Performance",
    "P0122": "Throttle/Pedal Position Sensor A Circuit Low Input",
    "P0123": "Throttle/Pedal Position Sensor A Circuit High Input",
    "P0125": "Insufficient Coolant Temperature for Closed Loop Fuel Control",
    "P0128": "Coolant Thermostat Malfunction",
    "P0130": "O2 Sensor Circuit Malfunction (Bank 1, Sensor 1)",
    "P0131": "O2 Sensor Circuit Low Voltage (Bank 1, Sensor 1)",
    "P0132": "O2 Sensor Circuit High Voltage (Bank 1, Sensor 1)",
    "P0133": "O2 Sensor Circuit Slow Response (Bank 1, Sensor 1)",
    "P0134": "O2 Sensor Circuit No Activity Detected (Bank 1, Sensor 1)",
    "P0135": "O2 Sensor Heater Circuit Malfunction (Bank 1, Sensor 1)",
    "P0136": "O2 Sensor Circuit Malfunction (Bank 1, Sensor 2)",
    "P0137": "O2 Sensor Circuit Low Voltage (Bank 1, Sensor 2)",
    "P0138": "O2 Sensor Circuit High Voltage (Bank 1, Sensor 2)",
    "P0140": "O2 Sensor Circuit No Activity Detected (Bank 1, Sensor 2)",
    "P0141": "O2 Sensor Heater Circuit Malfunction (Bank 1, Sensor 2)",
    "P0171": "System Too Lean (Bank 1)",
    "P0172": "System Too Rich (Bank 1)",
    "P0174": "System Too Lean (Bank 2)",
    "P0175": "System Too Rich (Bank 2)",
    "P0201": "Injector Circuit Malfunction — Cylinder 1",
    "P0202": "Injector Circuit Malfunction — Cylinder 2",
    "P0203": "Injector Circuit Malfunction — Cylinder 3",
    "P0204": "Injector Circuit Malfunction — Cylinder 4",
    "P0300": "Random/Multiple Cylinder Misfire Detected",
    "P0301": "Cylinder 1 Misfire Detected",
    "P0302": "Cylinder 2 Misfire Detected",
    "P0303": "Cylinder 3 Misfire Detected",
    "P0304": "Cylinder 4 Misfire Detected",
    "P0325": "Knock Sensor 1 Circuit Malfunction",
    "P0335": "Crankshaft Position Sensor A Circuit Malfunction",
    "P0340": "Camshaft Position Sensor A Circuit Malfunction",
    "P0400": "Exhaust Gas Recirculation Flow Malfunction",
    "P0401": "Exhaust Gas Recirculation Flow Insufficient Detected",
    "P0402": "Exhaust Gas Recirculation Flow Excessive Detected",
    "P0420": "Catalyst System Efficiency Below Threshold (Bank 1)",
    "P0430": "Catalyst System Efficiency Below Threshold (Bank 2)",
    "P0440": "Evaporative Emission Control System Malfunction",
    "P0442": "Evaporative Emission Control System Leak Detected (small leak)",
    "P0445": "Evaporative Emission Control System Purge Control Valve Circuit Shorted",
    "P0455": "Evaporative Emission Control System Leak Detected (gross leak)",
    "P0500": "Vehicle Speed Sensor Malfunction",
    "P0505": "Idle Control System Malfunction",
    "P0506": "Idle Control System RPM Lower Than Expected",
    "P0507": "Idle Control System RPM Higher Than Expected",
    "P0560": "System Voltage Malfunction",
    "P0600": "Serial Communication Link Malfunction",
    "P0601": "Internal Control Module Memory Check Sum Error",
    "P0602": "Control Module Programming Error",
    "P0606": "ECM/PCM Processor Fault",
    "P0700": "Transmission Control System Malfunction",
    "P0705": "Transmission Range Sensor Circuit Malfunction",
    "P0715": "Input/Turbine Speed Sensor Circuit Malfunction",
    "P0720": "Output Speed Sensor Circuit Malfunction",
    "P0730": "Incorrect Gear Ratio",
    "P0740": "Torque Converter Clutch Circuit Malfunction",
    "P0741": "Torque Converter Clutch Circuit Performance or Stuck Off",
    "P1100": "MAF Sensor Intermittent",
    "P1120": "Throttle Position Sensor Out of Range",
    "P1130": "Lack of HO2S-11 Switch, Fuel Trim at Limit",
    "P1150": "Lack of HO2S-21 Switch, Fuel Trim at Limit",
    "P1300": "Igniter Circuit Malfunction",
    "P1500": "Starter Signal Circuit Malfunction",
    "P1600": "ECM Battery Feed Malfunction",
    "P1792": "ECM to TCM Communication Error",
    "U0100": "Lost Communication With ECM/PCM",
    "U0101": "Lost Communication With TCM",
    "U0121": "Lost Communication With Anti-Lock Brake System Control Module",
    "U0140": "Lost Communication With Body Control Module",
}


class DtcDatabase:
    """Read-only DTC descriptions with connection ownership by constructing thread.

    The UI uses its module-level instance. A diagnostic worker constructs and
    closes a separate instance on its own thread; mode=ro does not remove
    SQLite thread affinity. Code lookup uses the database index.

    Example:
        >>> db = DtcDatabase("dtc_descriptions.db")
        >>> db.describe("B7F805")
        'Connection head unit to DAB L-band antenna base: line disconnection'
        >>> db.describe("ZZZZZZ")
        None
    """

    def __init__(self, db_path: str = "dtc_descriptions.db") -> None:
        """Open the DTC database in read-only mode.

        G-14: If the database file is missing, the singleton still
        initializes but all lookups return None / fallback values.
        The app shows a user-facing warning on the diagnostics page.

        Args:
            db_path: Path to the SQLite database file.
        """
        self._missing = False
        try:
            self.conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        except sqlite3.OperationalError:
            self.conn = sqlite3.connect(":memory:")
            self._missing = True
            logging.getLogger(__name__).warning(
                "DTC database not found at %s — descriptions unavailable", db_path
            )

    def describe(self, code: str) -> str | None:
        """Look up a DTC code. Returns English text, falls back to German.

        Normalises the input by uppercasing and stripping 0x/0X prefixes.
        If the database is missing, falls back to OBD2 codes only.

        Args:
            code: DTC code as hex string (e.g. "B7F805", "0x8040BD").

        Returns:
            English description string, German fallback, or None if not found.

        Example:
            >>> db.describe("B7F805")
            'Connection head unit to DAB L-band antenna base: line disconnection'
        """
        code = code.upper().replace("0X", "").replace("0x", "")

        if self._missing:
            return _OBD2_CODES.get(code)

        row = self.conn.execute(
            "SELECT text_en, text_de FROM dtc_descriptions WHERE code = ? LIMIT 1",
            (code,),
        ).fetchone()

        if row:
            text: str | None = row[0] or row[1]
            return text

        return _OBD2_CODES.get(code)

    def describe_for_ecu(self, code: str, ecu: str) -> str | None:
        """Return a fault-location text only for an exact stored ECU name.

        Do not substitute a fault-type/measurement dictionary entry or another
        ECU's text. Missing aliases and extraction collisions stay unresolved.
        """
        if self._missing:
            return None
        row = self.conn.execute(
            "SELECT text_en, text_de FROM dtc_descriptions "
            "WHERE code = ? AND table_type = 'FORTTEXTE' AND UPPER(ecu) = ?",
            (code.upper().removeprefix("0X"), ecu.upper()),
        ).fetchone()
        return (row[0] or row[1]) if row else None

    def describe_with_ecu(self, code: str) -> tuple[str, str] | None:
        """Return (description, ecu_name) tuple or None if not found.

        Args:
            code: DTC code as hex string.

        Returns:
            Tuple of (description, ecu_name) or None.

        Example:
            >>> result = db.describe_with_ecu("8040BD")
            >>> result[0]  # description
            'Terminal 30F reset or shutdown'
            >>> result[1]  # ecu
            'BDC'
        """
        if self._missing:
            desc = _OBD2_CODES.get(code.upper().replace("0X", "").replace("0x", ""))
            return (desc, "") if desc else None
        code = code.upper().replace("0X", "").replace("0x", "")

        row = self.conn.execute(
            "SELECT text_en, text_de, ecu FROM dtc_descriptions WHERE code = ? LIMIT 1",
            (code,),
        ).fetchone()

        if row:
            return (row[0] or row[1], row[2])
        return None

    def fault_type(self, type_code: str) -> str | None:
        """Describe a fault type byte from the DTC status mask (FARTTEXTE table).

        Args:
            type_code: Fault type byte as hex string (e.g. "08").

        Returns:
            Description string or None if not found.

        Example:
            >>> db.fault_type("08")
            'implausible signal or value'
        """
        if self._missing:
            return None
        row = self.conn.execute(
            "SELECT text_en, text_de FROM dtc_descriptions "
            "WHERE code = ? AND table_type = 'FARTTEXTE' LIMIT 1",
            (type_code.upper(),),
        ).fetchone()
        return (row[0] or row[1]) if row else None


# Module-level singleton — loaded once at app startup.
# Usage: from app.dtc_db import dtc_db
dtc_db = DtcDatabase()
