"""Compile read-only component contracts from the catalog and canonical programs."""

import argparse
import sys
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.ediabas import JobEngine  # noqa: E402
from app.ista_data import DataFormatError, read_group_assignments, uds_variant_map  # noqa: E402
from scripts.recover_ista_texts import query, sha256_file  # noqa: E402
from scripts.recover_power_readers import _Peer, _run, _table, _write  # noqa: E402

# Compare the complete reviewed function/result/enumeration tables before sharing a decoder.
REFERENCES = {
    "WASCHWASSERSTAND": ("bdc", "washer"),
    "STATUS_ANT_QFS": ("entrynav", "radio"),
    "BREMSFLUESSIGKEITSSCHALTER": ("dsc_i1", "brake"),
    "TEMP_INNEN_UNBELUEFTET": ("ihx_i1", "climate"),
    "TEMP_VERDAMPFER_WERT": ("ihx_i1", "climate"),
}
REFERENCE_SHA256 = {
    "bdc": "68d093538e262a3ee431e62812d3871335446db00c99af5334e3f1887bb94666",
    "dsc_i1": "c0ba86109f340c9a89aad28f4c7f948af171abe227b7e2401ace78c4e4d8e5e8",
    "entrynav": "8adf15810a89fcc46a0814b61e40d33d02bc9ddbc2a3641819557f0d208bae67",
    "ihx_i1": "0e3274ef88a0e4b2edbdaca361ebc0294417f0c8cd295f5189099bfa838c29e5",
}
SIZE = {"char": 1, "int": 2, "long": 4}
CATALOG = "247682de1535d6e6aeef7d641001a7bc253410f198f130111eb01785213ee28a"


def demo_reads(name: str) -> dict[str, str]:
    """Return the synthetic readings for a bundled DEMO ECU."""
    return {
        "BDC": {"D357": "011234", "4F0E": "03"},
        "DSC_I1": {"DC1F": "01"},
        "IHX_I1": {"D85C": "16", "D95C": "09"},
        "NBT": {"D010": "0c08012d00017d40"},
    }.get(name.upper(), {})


def _fixed(db: Path, reader: Path) -> list[dict]:
    args = ",".join(f"'{arg}'" for arg in REFERENCES)
    # RetrieveFunctionDefinition evaluates the fixed-function/structure IDs on the
    # identified variant route. Group rules apply to independent group selection.
    ids = "v.id,rv.id,s.id,f.id,j.id,p.id"
    shortlist = query(
        reader,
        db,
        f"""SELECT DISTINCT r.id FROM xep_ecuparameters p
                      JOIN xep_refecuparameters r ON r.ecuparameterid=p.id
                      WHERE p.paramvalue IN ({args}) AND p.name='P2'""",
    )
    fixed_ids = ",".join(str(int(row["ID"])) for row in shortlist)
    sql = f"""
    SELECT DISTINCT upper(v.name) variant, f.id fixed, j.id job_id, s.id structure,
           rv.id reference, p.paramvalue arg
    FROM xep_ecuparameters p JOIN xep_refecuparameters rp ON rp.ecuparameterid=p.id
    JOIN xep_ecufixedfunctions f ON f.id=rp.id
    JOIN xep_ecufuncstructures s ON s.id=f.parentid
    JOIN xep_refecufuncstructs rs ON rs.ecufuncstructid=s.id
    JOIN xep_refecuvariants rv ON rv.id=rs.id JOIN xep_ecuvariants v ON v.id=rv.ecuvariantid
    JOIN xep_ecugroups g ON g.id=v.ecugroupid JOIN xep_refecujobs rj ON rj.id=f.id
    JOIN xep_ecujobs j ON j.id=rj.ecujobid AND j.id=p.ecujobid
    WHERE f.id IN ({fixed_ids}) AND p.name='P2' AND p.paramvalue IN ({args}) AND rp.phase='Main'
      AND j.name='STATUS_LESEN' AND rj.rank=1 AND rj.phase='Main' AND f.activation=0
      AND s.parentid=0 AND f.steuergeraetefunktionenrelevan=1
      AND (SELECT count(*) FROM xep_refecujobs x WHERE x.id=f.id)=1
      AND (SELECT count(*) FROM xep_refecuparameters x WHERE x.id=f.id)=2
      AND EXISTS (SELECT 1 FROM xep_refecuparameters x JOIN xep_ecuparameters a
          ON a.id=x.ecuparameterid WHERE x.id=f.id AND x.phase='Main' AND a.ecujobid=j.id
          AND a.name='P1' AND a.paramvalue='ARG'
          AND NOT EXISTS (SELECT 1 FROM xep_rules_include inc WHERE inc.id=a.id))
      AND NOT EXISTS (SELECT 1 FROM xep_rules x WHERE x.id IN ({ids}))
      AND NOT EXISTS (SELECT 1 FROM xep_rules_include x WHERE x.id IN ({ids}))
      AND NOT EXISTS (SELECT 1 FROM xep_refecuresults rr JOIN xep_rules x ON x.id=rr.ecuresultid
                      WHERE rr.id=f.id)
      AND NOT EXISTS (SELECT 1 FROM xep_refecuparameters rp2 JOIN xep_rules x
                      ON x.id=rp2.ecuparameterid WHERE rp2.id=f.id)
      AND coalesce(f.preparingoperatortext_engb,'')=''
      AND coalesce(f.processingoperatortext_engb,'')=''
      AND coalesce(f.postoperatortext_engb,'')=''
    """
    for alias in ("g", "v", "f"):
        for col in ("validfrom", "validto"):
            sql += f" AND coalesce({alias}.{col},'') IN ('','0001-01-01 00:00:00')"
    return query(reader, db, sql + " ORDER BY variant,arg,fixed")


@lru_cache(maxsize=128)
def _functions(path: Path) -> dict:
    return {row["ARG"]: row for row in _table(path, "SG_FUNKTIONEN")}


def _layout(path: Path, arg: str) -> tuple[list, dict, int]:
    f = _functions(path)[arg]
    if "22" not in f["SERVICE"].split(";"):
        raise ValueError("Expected a read-only branch")
    fields = [f] if f["RES_TABELLE"] == "-" else _table(path, f["RES_TABELLE"])
    enums = {row["NAME"]: _table(path, row["NAME"]) for row in fields if row["NAME"] != "-"}
    length = sum(SIZE[row["DATENTYP"].split()[-1]] for row in fields)
    return fields, enums, length


def build(rheingold: Path, reader: Path, output: Path) -> None:
    """Bind each admitted source row to an exact identity, decoder and single native read."""
    db, jobs = rheingold / "SQLiteDBs/DiagDocDb.sqlite", rheingold / "Ecu"
    if sha256_file(db) != CATALOG:
        raise ValueError("Unreviewed diagnostic catalog")
    for name, digest in REFERENCE_SHA256.items():
        if sha256_file(jobs / (name + ".prg")) != digest:
            raise ValueError(f"Unreviewed reference layout for {name}")
    variants = uds_variant_map(read_group_assignments(jobs / "t_grtb.prg"))
    profiles: dict = {}
    admitted: dict[str, dict[str, dict]] = {}
    for row in _fixed(db, reader):
        name, arg = row["variant"], row["arg"]
        ref, group = REFERENCES[arg]
        src, ref_file = jobs / (name.lower() + ".prg"), jobs / (ref + ".prg")
        if name not in variants.values() or not src.is_file():
            continue
        try:
            if _layout(src, arg) != _layout(ref_file, arg):
                continue
        except (KeyError, DataFormatError):
            continue
        spec = admitted.setdefault(name, {}).setdefault(arg, {"group": group, "catalog": []})
        spec["catalog"].append(row)
    # The body controller provides the stored IBS reason in its exact service-22
    # function and enumeration. This variant-specific record has no fixed-function row.
    admitted["BDC"]["IBS_WAKEUP_GRUND"] = {"group": "wake"}
    for name, arguments in sorted(admitted.items()):
        path = jobs / (name.lower() + ".prg")
        selectors = sorted(key for key, variant in variants.items() if variant == name)
        addresses = {int(key.split()[0], 16) for key in selectors}
        if len(addresses) != 1:
            continue
        peer = _Peer(addresses.pop())
        engine = JobEngine(peer)
        try:
            engine.load(path, jobs)
            for arg, spec in arguments.items():
                request = "22" + _functions(path)[arg]["ID"][2:].lower()
                size = _layout(path, arg)[2]
                spec.update(job="STATUS_LESEN", args=f"ARG;{arg}", request=request, size=size)
                result = _run(engine, peer, spec, bytes(size))
                fields = _layout(path, arg)[0]
                if len(result.sets) != 1 or not all(
                    field["RESULTNAME"] in result.sets[0] for field in fields
                ):
                    raise ValueError(f"Native result set changed for {name}/{arg}")
        finally:
            engine.close()
        profiles[name] = {
            "sha256": sha256_file(path),
            "selectors": selectors,
            "readers": arguments,
        }
    _write(output, {"schema": 1, "catalog_sha256": CATALOG, "profiles": profiles})


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--rheingold", type=Path, required=True)
    cli.add_argument("--reader", type=Path, required=True)
    cli.add_argument("--output", type=Path, required=True)
    opts = cli.parse_args()
    build(opts.rheingold, opts.reader, opts.output)
