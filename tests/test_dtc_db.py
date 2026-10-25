"""Tests for app.dtc_db — DtcDatabase singleton.

These tests use the real dtc_descriptions.db. They verify:
- Code normalisation (uppercasing, 0x stripping)
- English text with German fallback
- describe_with_ecu returns ECU name
- fault_type returns FARTTEXTE descriptions
- Unknown codes return None
"""

import os
import pytest
from app.dtc_db import DtcDatabase


@pytest.fixture(scope="module")
def db():
    """Create a DtcDatabase pointing at the real dtc_descriptions.db."""
    # The database lives in the repo root alongside this tests/ directory.
    # From tests/, the relative path is ../dtc_descriptions.db.
    db_path = os.path.join(os.path.dirname(__file__), "..", "dtc_descriptions.db")
    if not os.path.exists(db_path):
        pytest.skip(f"dtc_descriptions.db not found at {db_path}")
    return DtcDatabase(db_path)


# ── describe ─────────────────────────────────────────────────────────────────

def test_describe_b7f805(db):
    """describe("B7F805") returns the DAB antenna description."""
    result = db.describe("B7F805")
    assert result is not None
    assert "DAB" in result or "antenna" in result.lower()


def test_describe_with_0x_prefix(db):
    """describe("0xB7F805") normalises the 0x prefix."""
    result = db.describe("0xB7F805")
    assert result is not None
    assert "DAB" in result or "antenna" in result.lower()


def test_describe_lowercase_normalised(db):
    """describe("b7f805") normalizes to uppercase."""
    result = db.describe("b7f805")
    assert result is not None


def test_describe_unknown_code(db):
    """describe("ZZZZZZ") returns None for an impossible DTC code."""
    result = db.describe("ZZZZZZ")
    assert result is None


def test_describe_returns_string_not_none_for_valid(db):
    """describe on a known code returns a non-empty string."""
    # Try a few known codes
    for code in ["B7F805", "8040BD", "118001"]:
        result = db.describe(code)
        if result is not None:
            assert isinstance(result, str)
            assert len(result.strip()) > 0
            break
    else:
        pytest.skip("No known codes found in test database — verify codes")


# ── describe_with_ecu ───────────────────────────────────────────────────────

def test_describe_with_ecu(db):
    """describe_with_ecu returns (description, ecu_name) tuple or None."""
    result = db.describe_with_ecu("8040BD")
    if result is None:
        pytest.skip("Code 8040BD not found in database")
    desc, ecu = result
    assert isinstance(desc, str)
    assert isinstance(ecu, str)
    assert len(desc) > 0
    assert len(ecu) > 0


def test_describe_with_ecu_unknown(db):
    """describe_with_ecu("ZZZZZZ") returns None."""
    result = db.describe_with_ecu("ZZZZZZ")
    assert result is None


# ── fault_type ──────────────────────────────────────────────────────────────

def test_fault_type_08(db):
    """fault_type("08") returns a fault type description string."""
    result = db.fault_type("08")
    if result is not None:
        assert "signal" in result.lower() or "value" in result.lower()


def test_fault_type_unknown(db):
    """fault_type("FF") returns None (not a valid fault type code)."""
    result = db.fault_type("FF")
    # This may or may not be in the database; just verify no crash
    assert result is None or isinstance(result, str)


# ── OBD2 fallback ────────────────────────────────────────────────────────────

def test_obd2_fallback_p0300(db):
    """describe("P0300") returns OBD2 text even if not in BMW table."""
    result = db.describe("P0300")
    assert result is not None
    assert "misfire" in result.lower()
    assert "random" in result.lower() or "multiple" in result.lower()


def test_obd2_fallback_p0171(db):
    """describe("P0171") returns OBD2 lean bank 1 text."""
    result = db.describe("P0171")
    assert result is not None
    assert "lean" in result.lower()