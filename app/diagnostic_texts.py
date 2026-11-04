"""Exact-variant diagnostic descriptions from the embedded plain text database.

The database is generated during development. Runtime needs only the ordinary
SQLite asset; it never opens research sources, decrypts data or invokes a tool.
"""

import logging
import sqlite3
from contextlib import closing
from pathlib import Path

from app.resources import resource_path

logger = logging.getLogger(__name__)
_MAX_ASSET_BYTES = 128 * 1024 * 1024
_MAX_CANDIDATES = 128


class DiagnosticTexts:
    """Read source-derived descriptions without sharing connections across threads.

    Each lookup owns and closes its read-only connection on the calling thread.
    Rule-conditioned candidates are not resolved by guessing a vehicle condition:
    only a single distinct candidate text is returned for an exact identity.
    """

    def __init__(self, path: Path | None = None) -> None:
        """Select the embedded data file or an explicit standalone data fixture."""
        self.path = path if path is not None else resource_path("coding_data/diagnostic_texts.db")

    def _texts(self, query: str, parameters: tuple[str | int, ...]) -> str:
        """Return a single invariant description, or empty for unavailable/ambiguous."""
        try:
            if not self.path.is_file() or self.path.stat().st_size > _MAX_ASSET_BYTES:
                return ""
            uri = self.path.resolve().as_uri() + "?mode=ro&immutable=1"
            with closing(sqlite3.connect(uri, uri=True)) as connection:
                if connection.execute("PRAGMA user_version").fetchone() != (1,):
                    raise ValueError("Unsupported diagnostic text schema")
                rows = connection.execute(query, parameters).fetchmany(_MAX_CANDIDATES + 1)
                if len(rows) > _MAX_CANDIDATES:
                    return ""
                texts = {str(row[0]).strip() for row in rows if row[0]}
                return texts.pop() if len(texts) == 1 else ""
        except (OSError, sqlite3.Error, ValueError):
            logger.warning("Embedded diagnostic text lookup unavailable", exc_info=True)
            return ""

    def describe(self, code: int, *, ecu: str, fault_type: str = "F", language: str = "en") -> str:
        """Return an exact variant/code/memory description in the requested language.

        Args:
            code: Numeric diagnostic code, independent of its display width.
            ecu: Identified variant name, never a marketing model or chassis hint.
            fault_type: Source memory datatype F (fault) or I (information).
            language: en requests English only; de requests German only.
        """
        if isinstance(code, bool) or not 0 <= code <= 0xFFFFFF or not ecu:
            return ""
        if fault_type not in {"F", "I"} or language not in {"en", "de"}:
            return ""
        column = "text_en" if language == "en" else "text_de"
        return self._texts(
            f"SELECT {column} FROM fault_texts "
            "WHERE variant=? COLLATE NOCASE AND code=? AND fault_type=? LIMIT 129",
            (ecu, code, fault_type),
        )

    def ecu_title(self, ecu: str, *, language: str = "en") -> str:
        """Return a sourced ECU title only when exact-name candidates agree."""
        if not ecu or language not in {"en", "de"}:
            return ""
        column = "text_en" if language == "en" else "text_de"
        return self._texts(
            f"SELECT {column} FROM ecu_titles WHERE variant=? COLLATE NOCASE LIMIT 129", (ecu,)
        )


diagnostic_texts = DiagnosticTexts()
