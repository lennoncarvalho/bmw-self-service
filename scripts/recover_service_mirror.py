"""Build the fitted electrochromic interior-mirror test from reviewed catalog and native jobs."""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.ediabas import JobEngine  # noqa: E402
from scripts.recover_ista_texts import query, sha256_file  # noqa: E402
from scripts.recover_power_readers import _Peer, _run, _table, _write  # noqa: E402

CATALOG = "247682de1535d6e6aeef7d641001a7bc253410f198f130111eb01785213ee28a"
FIXED = {
    "BDC": (20000155893359, 5),
    "FEM_20": (20000350471818, 5),
    "BDC_G05": (20000374085724, 10),
    "BCP_SP21": (20000634214574, 10),
}


def compile_variant(catalog: Path, reader: Path, path: Path, fixed: int, seconds: int) -> dict:
    """Require the exact applicable variant route, Main job, fitment reader and ECU timer."""
    name = path.stem.upper()
    records = query(
        reader,
        catalog,
        f"""SELECT v.ID variant_id, rv.ID link_id, s.ID structure_id, f.ID fixed_id,
                   g.DIAGNOSTIC_ADDRESS address
              FROM XEP_ECUVARIANTS v JOIN XEP_ECUGROUPS g ON g.ID=v.ECUGROUPID
              JOIN XEP_REFECUVARIANTS rv ON rv.ECUVARIANTID=v.ID
              JOIN XEP_REFECUFUNCSTRUCTS rs ON rs.ID=rv.ID
              JOIN XEP_ECUFUNCSTRUCTURES s ON s.ID=rs.ECUFUNCSTRUCTID
              JOIN XEP_ECUFIXEDFUNCTIONS f ON f.PARENTID=s.ID
             WHERE upper(v.NAME)='{name}' AND f.ID={fixed} AND s.PARENTID=0
               AND f.ACTIVATION=0 AND f.ACTIVATION_DURATION_MS=0
               AND f.STEUERGERAETEFUNKTIONENRELEVAN=1
               AND f.VALIDFROM='0001-01-01 00:00:00' AND f.VALIDTO=f.VALIDFROM
               AND v.VALIDFROM=f.VALIDFROM AND v.VALIDTO=f.VALIDTO
               AND NOT EXISTS(SELECT 1 FROM XEP_RULES WHERE ID IN (v.ID,rv.ID,s.ID,f.ID))
               AND NOT EXISTS(SELECT 1 FROM XEP_RULES_INCLUDE WHERE ID IN (v.ID,rv.ID,s.ID,f.ID))
        """,
    )
    phases = query(
        reader,
        catalog,
        f"""SELECT r.PHASE phase,r.RANK rank,j.ID job_id,j.NAME job,p.NAME param,p.PARAMVALUE value
              FROM XEP_REFECUJOBS r JOIN XEP_ECUJOBS j ON j.ID=r.ECUJOBID
              LEFT JOIN XEP_ECUPARAMETERS p ON p.ECUJOBID=j.ID
             WHERE r.ID={fixed} ORDER BY p.NAME""",
    )
    if (
        len(records) != 1
        or len({(r["phase"], r["rank"], r["job_id"], r["job"]) for r in phases}) != 1
        or phases[0]["phase"] != "Main"
        or phases[0]["rank"] != 1
        or phases[0]["job"] != "STEUERN"
        or [(r["param"], r["value"]) for r in phases]
        != [("P1", "ARG"), ("P2", "EC_SPIEGEL_ABBLENDEN"), ("P3", str(seconds))]
    ):
        raise ValueError(f"Mirror applicability or fixed job changed for {name}")
    functions = {r["ARG"]: r for r in _table(path, "SG_FUNKTIONEN")}
    present = functions["EC_SPIEGEL_VORHANDEN"]
    dim = functions["EC_SPIEGEL_ABBLENDEN"]
    (args,) = _table(path, dim["ARG_TABELLE"])
    (result,) = _table(path, dim["RES_TABELLE"])
    if (
        args["EINHEIT"] != "s"
        or args["DATENTYP"] != "unsigned char"
        or result["EINHEIT"] != "%"
        or result["DATENTYP"] != "unsigned char"
        or present["EINHEIT"] != "0/1"
    ):
        raise ValueError(f"Mirror units or timer changed for {name}")
    peer = _Peer(records[0]["address"])
    engine = JobEngine(peer)
    profile = {
        "source": {**records[0], "job_id": phases[0]["job_id"]},
        "sha256": sha256_file(path),
        "seconds": seconds,
    }
    try:
        engine.load(path, ecu_dir=path.parent)
        for key, row, field, values in (
            ("present", present, present["RESULTNAME"], (0, 1)),
            ("state", dim, result["RESULTNAME"], (0, 1, 100)),
        ):
            spec = {
                "request": f"22{int(row['ID'], 16):04x}",
                "job": "STATUS_LESEN",
                "args": "ARG;" + row["ARG"],
                "field": field,
            }
            for value in values:
                sets = _run(engine, peer, spec, bytes([value])).sets
                if len(sets) != 1 or sets[0].get(field) != value:
                    raise ValueError(f"Mirror {key} readback changed for {name}")
            profile[key] = spec
        peer.request = bytes.fromhex(f"2e{int(dim['ID'], 16):04x}{seconds:02x}")
        peer.response = b"\x6e" + peer.request[1:3]
        peer.sent = []
        command = ";".join(r["value"] for r in phases)
        native = engine.run_job(phases[0]["job"], command, timeout=2, grant=frozenset({0x2E}))
        if peer.sent != [peer.request] or native.status != "OKAY" or len(native.sets) != 1:
            raise ValueError(f"Mirror activation encoding changed for {name}")
        profile["start"] = {
            "job": phases[0]["job"],
            "args": command,
            "request": peer.request.hex(),
            "reply": peer.response.hex(),
        }
        return profile
    finally:
        engine.close()


def main() -> None:
    """Generate the standalone versioned mirror definitions."""
    parser = argparse.ArgumentParser(description=__doc__)
    for option in ("rheingold", "reader", "output"):
        parser.add_argument("--" + option, type=Path, required=True)
    args = parser.parse_args()
    catalog = args.rheingold / "SQLiteDBs/DiagDocDb.sqlite"
    if sha256_file(catalog) != CATALOG:
        raise ValueError("Mirror service catalog changed")
    profiles = {
        name: compile_variant(
            catalog, args.reader, args.rheingold / "Ecu" / (name.lower() + ".prg"), fixed, seconds
        )
        for name, (fixed, seconds) in FIXED.items()
    }
    _write(args.output, {"schema": 1, "catalog_sha256": CATALOG, "profiles": profiles})


if __name__ == "__main__":
    main()
