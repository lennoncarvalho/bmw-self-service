"""Compile applicable blade-service instructions and verify exact position readers offline."""

import argparse
import hashlib
import io
import sqlite3
import struct
import sys
from collections import defaultdict
from contextlib import closing
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.ediabas import JobEngine  # noqa: E402
from app.ista_data import normalize_series, read_group_assignments, uds_variant_map  # noqa: E402
from scripts.recover_ista_texts import query, sha256_file  # noqa: E402
from scripts.recover_power_readers import _Peer, _run, _table, _write  # noqa: E402
from scripts.recover_vehicle_models import SCHEMA, SERIES_SCHEMA, indexed_rows  # noqa: E402

# Reviewed repair instruction, owner procedure and exact EN-GB XML content digest.
DOCUMENTS = {
    2000006607246: (
        "accessory",
        "eae21757299699d8e0142f612799b51fd1b11ded46b033a621ec8a8754f56f9c",
    ),
    2000009416139: (
        "accessory",
        "1e22a09667aa8a1362e6446ae159574b4d392c89452d1bd11e5eea3ae7e3912e",
    ),
    2000010406898: (
        "accessory",
        "8e3d5623efb22014a56bd740300099b482a2e96d36e671850e2d3ad9a6596c18",
    ),
    2000011680222: (
        "accessory",
        "9cb573c7d847c734b560efdf797dc39c937d48f72f066836cf604761f38bff3b",
    ),
    2000012946159: (
        "accessory",
        "7af98faecf67f4a166b245c21c58f11c1fc32f2aeef314e9900f0ff322c266f4",
    ),
    2000014532700: (
        "standby_down",
        "130274e2553035896625f506a175df23368b878c07d738143416a41349892856",
    ),
    2000033792335: (
        "standby_down",
        "1fa73eea714a709f41720f368861270d542de7e306f402dd0e7dde270054f179",
    ),
    2000038893400: (
        "standby_down",
        "ce63d509956f6e68d81765805aafca6fe36964928536ecd9e65c8ba362cd54cb",
    ),
    2000039270795: (
        "standby_down",
        "1e1816a01524f60beb7cee409f312ec9ab859a3f6703b66b5ac3853f119a5b3d",
    ),
    2000039457527: (
        "standby_down",
        "551032a815330680079dc09d50659e02ecf1e0b67ea7461e28dfe77d341b13ca",
    ),
    2000043254676: (
        "standby_down",
        "1296d77b06eb8e27dae99730f52528c3b9d04d9fccef3ea0a88fd2858e8143ca",
    ),
    2000045298767: (
        "standby_up",
        "9f2c744acbe50fb1bd4ec6d25d7f37da59d21c2b282069279b3f721baa5ead87",
    ),
    2000070728812: (
        "standby_down",
        "225fb73f053aaedff519d98826945fe5a98190df83d011f1156f566fabcde02e",
    ),
}


def rule_types(raw: bytes, by_characteristic: dict[tuple[int, int], set[str]]) -> set[str]:
    """Evaluate the complete positive characteristic intersections and unions."""
    stream = io.BytesIO(raw)

    def read() -> set[str]:
        opcode = stream.read(1)
        if opcode == b"\x11":
            return by_characteristic.get(struct.unpack("<QQ", stream.read(16)), set())
        if opcode not in (b"\x01", b"\x02"):
            raise ValueError("Unreviewed wiper instruction predicate")
        (count,) = struct.unpack("<I", stream.read(4))
        if not 1 <= count <= 128:
            raise ValueError("Invalid wiper instruction predicate")
        alternatives = [read() for _ in range(count)]
        return set.intersection(*alternatives) if opcode == b"\x01" else set.union(*alternatives)

    result = read()
    if stream.read(1):
        raise ValueError("Unconsumed repair predicate")
    return result


def supplement_types(rheingold: Path, grouped: dict, categories: dict) -> tuple[dict, dict]:
    """Translate explicit KIS brand/body/series through agreeing passenger-car catalogue rows."""
    keys: dict = defaultdict(set)
    row_ids: dict = defaultdict(list)
    sources = {}
    for path in sorted((rheingold / "PSdZ/kiswb").glob("*/KIS.script")):
        script = path.read_text()
        if not {SCHEMA, SERIES_SCHEMA} <= set(script.splitlines()):
            raise ValueError("Unreviewed vehicle-type schema")
        data = path.with_name("KIS.data")
        series_ids = {r[0]: r[1] for r in indexed_rows(data, script, "EBR", "isis", 3)}
        package = path.parent.name
        sources[package] = {"script": sha256_file(path), "data": sha256_file(data)}
        for row_id, code, series_id, _, attributes, pdm in indexed_rows(
            data, script, "FAHRZEUGTYP", "isisss", 2
        ):
            props, cross = [
                dict(s.split("=", 1) for s in (field or "").split(";") if "=" in s)
                for field in (attributes, pdm)
            ]
            triple = (props.get("MARKE"), props.get("EBR"), props.get("KFORM"))
            if (
                not all(triple)
                or series_ids.get(series_id) != triple[1]
                or triple
                != (cross.get("TYP_MARKE"), cross.get("TYP_ENTW_BEZ"), cross.get("TYP_KAROSS"))
            ):
                keys[code].add(None)
                continue
            keys[code].add(triple)
            row_ids[code].append((package, row_id))
    translations: dict = defaultdict(set)
    for code, variants in keys.items():
        if len(variants) != 1 or None in variants or code not in grouped:
            continue
        entry = grouped[code]
        if any(len(entry[root]) != 1 for root in ("ids", 53078923, 53088651, 53046411, 53073547)):
            continue
        (triple,) = variants
        ((series_id, series),) = entry[53088651]
        ((brand_id, _),) = entry[53078923]
        ((_, body),) = entry[53046411]
        ((_, product),) = entry[53073547]
        if triple[1:] == (series, body):
            translations[triple].add((brand_id, series_id, product))
    added = {}
    for code, variants in keys.items():
        # Existing type keys, including ambiguous ones, retain their catalogue decision.
        if code in grouped or len(variants) != 1 or None in variants:
            continue
        (triple,) = variants
        matches = translations[triple]
        if len(matches) != 1:
            continue
        ((brand, series_id, product),) = matches
        if product != "P" or brand not in (53086475, 66786659595):
            continue
        series = normalize_series(triple[1])
        if not series.startswith(("F", "G", "U", "I")):
            continue
        model = f"{series} {code}"
        categories[53078923, brand].add(model)
        categories[53088651, series_id].add(model)
        added[model] = sorted(row_ids[code])
    return added, sources


def applicability(rheingold: Path, reader: Path) -> tuple[dict, dict, dict]:
    """Require one exact vehicle type and all validity predicates for the reviewed document."""
    database = rheingold / "SQLiteDBs/DiagDocDb.sqlite"
    rows = query(
        reader,
        database,
        """
        SELECT t.ID tid,t.NAME code,c.ID value,c.PARENTID root,c.NAME label
        FROM XEP_CHARACTERISTICS t JOIN XEP_VEHICLES v ON v.TYPEKEYID=t.ID
        JOIN XEP_CHARACTERISTICS c ON c.ID=v.CHARACTERISTICID
        WHERE t.PARENTID=53513611 AND c.PARENTID IN (53078923,53088651,53046411,53073547)
        ORDER BY t.ID,c.ID
    """,
    )
    grouped = defaultdict(lambda: defaultdict(set))
    for row in rows:
        entry = grouped[row["code"]]
        entry["ids"].add(row["tid"])
        entry[row["root"]].add((row["value"], row["label"]))
    by_characteristic = defaultdict(set)
    for code, entry in grouped.items():
        if len(entry["ids"]) != 1 or len(entry[53088651]) != 1 or len(entry[53078923]) != 1:
            continue
        ((series_id, series),) = entry[53088651]
        ((brand_id, _),) = entry[53078923]
        if brand_id not in (53086475, 66786659595) or not series.startswith(("F", "G", "U", "I")):
            continue
        key = f"{normalize_series(series)} {code}"
        by_characteristic[53088651, series_id].add(key)
        by_characteristic[53078923, brand_id].add(key)

    extra, packages = supplement_types(rheingold, grouped, by_characteristic)
    ids = ",".join(map(str, DOCUMENTS))
    documents = query(
        reader,
        database,
        f"""
        SELECT i.ID coordinate,c.CONTENT_ENGB text_id,hex(x.RULE) predicate
        FROM XEP_INFOOBJECTS i JOIN XEP_REFCONTENTS link ON link.ID=i.CONTROLID
        JOIN XEP_IOCONTENTS c ON c.CONTROLID=link.CONTENTCONTROLID
        JOIN XEP_RULES x ON x.ID=i.ID WHERE i.ID IN ({ids})
        AND i.VALIDFROM='0001-01-01 00:00:00' AND i.VALIDTO=i.VALIDFROM
        AND c.EXPIRYDATE=i.VALIDFROM AND c.LAUNCHDATE=i.VALIDFROM
        AND NOT EXISTS(SELECT 1 FROM XEP_RULES WHERE ID IN(c.ID,link.ID))
        AND NOT EXISTS(SELECT 1 FROM XEP_RULES_INCLUDE WHERE ID IN(c.ID,link.ID))
        ORDER BY i.ID
    """,
    )
    includes = query(
        reader,
        database,
        f"""
        SELECT DISTINCT ID coordinate,hex(RULE) predicate FROM XEP_RULES_INCLUDE
        WHERE ID IN ({ids})
    """,
    )
    if len(documents) != len(DOCUMENTS):
        raise ValueError("Unresolved blade repair instructions")
    model_documents = defaultdict(list)
    sources = {}
    xml_path = rheingold / "SQLiteDBs/xmlvalueprimitive_ENGB.sqlite"
    with closing(sqlite3.connect(xml_path.resolve().as_uri() + "?mode=ro", uri=True)) as db:
        for document in documents:
            coordinate = document["coordinate"]
            guide, digest = DOCUMENTS[coordinate]
            ((xml,),) = db.execute(
                "SELECT data FROM xmlvalueprimitive WHERE id=? AND deleted=0",
                (document["text_id"],),
            ).fetchall()
            if hashlib.sha256(xml.encode()).hexdigest() != digest:
                raise ValueError("Wiper repair instructions changed")
            models = rule_types(bytes.fromhex(document["predicate"]), by_characteristic)
            for rule in includes:
                if rule["coordinate"] == coordinate:
                    models &= rule_types(bytes.fromhex(rule["predicate"]), by_characteristic)
            sources[coordinate] = {"guide": guide, "content": document["text_id"], "sha256": digest}
            for model in sorted(models):
                model_documents[model].append(coordinate)
    # Each source for a type must specify the same entry/return.
    models = {
        model: coords
        for model, coords in model_documents.items()
        if len({DOCUMENTS[c][0] for c in coords}) == 1
    }
    supplements = {k: v for k, v in extra.items() if k in models}
    return (
        models,
        sources,
        {
            "rows": supplements,
            "packages": {name: packages[name] for rows in supplements.values() for name, _ in rows},
        },
    )


def profiles(ecus: Path) -> dict:
    """Verify each independently selected canonical variant's exact native position values."""
    assignment = uds_variant_map(read_group_assignments(ecus / "t_grtb.prg"))
    profiles = {}
    reviewed = {
        "BCP_SP21": "5c37a2c5bba34b410e2b7687e5fb21fe29c5f309ebbccd44dae457b4cf13ce8f",
        "BDC": "68d093538e262a3ee431e62812d3871335446db00c99af5334e3f1887bb94666",
        "BDC_G05": "03eda3f6ad72455cf5943f1df77f8cda30bb14eeb313c44a9e52a57c75794056",
        "BDC_G11": "8733bab7214a25b5804952ca7d1e40839e152c9fdfedd903684daf1ea2a4ba54",
        "FEM_20": "b00015f5021e068eafdea0109df2bf87023ae59132a8b97222e4dc72b013f67b",
    }
    for name, digest in reviewed.items():
        path = ecus / (name.lower() + ".prg")
        if sha256_file(path) != digest:
            raise ValueError(f"Unreviewed wiper position definition for {name}")
        selectors = [key for key, value in assignment.items() if value == name]
        (address,) = {int(k.split()[0], 16) for k in selectors}
        functions = {r["ARG"]: r for r in _table(path, "SG_FUNKTIONEN")}
        if name in ("BDC_G05", "BCP_SP21"):
            definitions = [
                (
                    "park_contact",
                    "WISCHER_FRONT_POSITION",
                    "STAT_FRONT_SCHEIBENWISCHER_POSITIONO",
                    ["IN RSK/Parkposition", "Ausserhalb RSK/Parkposition"],
                )
            ]
        else:
            definitions = [
                ("service", "WISCHER_FRONT_SERVICE", "STAT_FRONTWISCHER_SERVICE_EIN", [0, 1]),
                ("park", "WISCHER_FRONT_RSK", "STAT_FRONTWISCHER_RSK_EIN", [0, 1]),
            ]
        readers = {}
        peer = _Peer(address)
        engine = JobEngine(peer)
        try:
            engine.load(path, path.parent)
            for key, arg, field, expected in definitions:
                row = functions[arg]
                if "22" not in row["SERVICE"].split(";"):
                    raise ValueError("Missing wiper read")
                job = {
                    "job": "STATUS_LESEN",
                    "args": "ARG;" + arg,
                    "request": f"22{int(row['ID'], 16):04x}",
                }
                for raw, value in enumerate(expected):
                    result = _run(engine, peer, job, bytes([raw]))
                    (data,) = result.sets
                    if data[field] != value:
                        raise ValueError("Wiper read field or meaning changed")
                readers[key] = {**job, "field": field, "values": expected}
        finally:
            engine.close()
        profiles[name] = {"sha256": digest, "selectors": selectors, "readers": readers}
    return profiles


def build(source: Path, reader: Path, output: Path) -> None:
    """Publish verified repair fitment and read-only status definitions."""
    models, documents, supplement = applicability(source, reader)
    if models.get("F048 JG31") != [2000012946159] or models.get("F048 HS71") != [2000012946159]:
        raise ValueError("Reviewed catalogue and supplemental vehicle-type matches changed")
    _write(
        output,
        {
            "schema": 1,
            "models": models,
            "documents": documents,
            "type_supplement": supplement,
            "profiles": profiles(source / "Ecu"),
            "catalog_sha256": sha256_file(source / "SQLiteDBs/DiagDocDb.sqlite"),
        },
    )


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--rheingold", type=Path, required=True)
    cli.add_argument("--reader", type=Path, required=True)
    cli.add_argument("--output", type=Path, required=True)
    args = cli.parse_args()
    build(args.rheingold, args.reader, args.output)
