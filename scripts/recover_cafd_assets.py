"""Recover supplied coding definition XML into a development-only verified export.

This follows the supplied Java resource/PIN/PKCS12/CMS chain without executing
reference classes. Requires the existing OpenSSL CLI and project Qt/PyCryptodome.
The app consumes a separate built catalogue; no source keys or tools are shipped.
"""

from __future__ import annotations

import argparse
import base64
import gzip
import hashlib
import io
import json
import os
import re
import subprocess
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad
from PySide6.QtGui import QImage

MAX_XML = 64 * 1024 * 1024


def digest(data: bytes) -> str:
    """Identify exact source/output bytes."""
    return hashlib.sha256(data).hexdigest()


def run(command: list[str], data: bytes | None = None) -> bytes:
    """Run an existing generic crypto tool without shell evaluation or target execution."""
    result = subprocess.run(command, input=data, capture_output=True, timeout=30, check=False)
    if result.returncode:
        raise ValueError(
            "Crypto decoding failed; the supplied key/certificate or format does not match"
        )
    if len(result.stdout) > MAX_XML:
        raise ValueError("Decoded crypto payload exceeds the development bound")
    return result.stdout


def image_payload(raw: bytes) -> bytes:
    """Decode the exact RGB low-two-bit resource encoding from ResourceParser."""
    if len(raw) > 16 * 1024 * 1024:
        raise ValueError("Resource image exceeds the source profile")
    image = QImage.fromData(raw)
    if image.isNull() or image.width() * image.height() > 16 * 1024 * 1024:
        raise ValueError("Resource image is invalid or too large")
    characters = []
    for y in range(1, image.height()):
        for x in range(1, image.width()):
            pixel = image.pixelColor(x, y)
            character = chr(
                ((pixel.red() & 3) | ((pixel.green() & 3) << 2) | ((pixel.blue() & 3) << 4)) + 32
            )
            if character == "_":
                return bytes.fromhex("".join(characters))
            if character not in "0123456789abcdefABCDEF":
                raise ValueError("Resource metadata is not the source hex profile")
            characters.append(character)
    raise ValueError("Resource image has no source terminator")


def license_keys(psdz: Path, temporary: Path, openssl: str) -> tuple[Path, Path]:
    """Decode the source licence and select its actual coding-encryption key pair."""
    resource = psdz / "bin/psdz/resource.jar"
    with zipfile.ZipFile(resource) as archive:
        names = ["bmw_logo.png", "bmw_mini_logo.png"]
        if any(archive.namelist().count(name) != 1 for name in names):
            raise ValueError("Source resource names are missing or ambiguous")
        encrypted, aes_key = [image_payload(archive.read(name)) for name in names]
    metadata = ET.fromstring(
        unpad(AES.new(aes_key, AES.MODE_CBC, bytes(16)).decrypt(encrypted), 16)
    )
    passphrases = {
        node.attrib["id"]: (node.text or "").strip() for node in metadata.findall(".//passphrase")
    }
    licence = ET.parse(psdz / "security/sec_security.lic").getroot()
    pin = hashlib.sha1(passphrases[licence.attrib["pid"]].encode()).hexdigest().upper()
    password = temporary / "pin"
    password.write_text(pin)
    password.chmod(0o600)
    pkcs12 = temporary / "licence.p12"
    pkcs12.write_bytes(base64.b64decode(licence.text or "", validate=True))
    pem = run(
        [
            openssl,
            "pkcs12",
            "-in",
            str(pkcs12),
            "-passin",
            "file:" + str(password),
            "-nodes",
            "-legacy",
        ]
    )
    private_keys = re.findall(
        rb"-----BEGIN PRIVATE KEY-----.*?-----END PRIVATE KEY-----", pem, re.S
    )
    certificates = re.findall(
        rb"-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----", pem, re.S
    )
    found = []
    for index, certificate in enumerate(certificates):
        subject = run([openssl, "x509", "-noout", "-subject"], certificate).decode()
        if not re.search(r"CN\s*=\s*Codier-Encrypt(?:,|\s*$)", subject):
            continue
        public = run([openssl, "x509", "-pubkey", "-noout"], certificate)
        certificate_public = run([openssl, "pkey", "-pubin", "-outform", "DER"], public)
        for key_index, key in enumerate(private_keys):
            key_public = run([openssl, "pkey", "-pubout", "-outform", "DER"], key)
            if certificate_public != key_public:
                continue
            key_path = temporary / f"private-{key_index}.pem"
            cert_path = temporary / f"certificate-{index}.pem"
            key_path.write_bytes(key)
            key_path.chmod(0o600)
            cert_path.write_bytes(certificate)
            found.append((key_path, cert_path))
    if len(found) != 1:
        raise ValueError("Source coding encryption certificate/private key is missing or ambiguous")
    return found[0]


def recover(psdz: Path, output: Path, *, openssl: str, include_fafp: bool = False) -> dict:
    """Export all supplied exact definitions with source and decoded identities."""
    if output.resolve().is_relative_to(psdz.resolve()):
        raise ValueError("Development output must be separate from source material")
    manifest = {"schema_version": 1, "sources": {}, "documents": {}}
    for name in ["bin/psdz/psdz-core.jar", "bin/psdz/resource.jar", "security/sec_security.lic"]:
        manifest["sources"][name] = digest((psdz / name).read_bytes())
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="coding-source-") as directory:
        key, certificate = license_keys(psdz, Path(directory), openssl)
        kinds = ["cafd"] + (["fafp"] if include_fafp else [])
        for kind in kinds:
            for source in sorted((psdz / "swe" / kind).iterdir()):
                if not source.is_file():
                    continue
                raw = source.read_bytes()
                root = ET.fromstring(raw)
                if root.attrib.get("isEncrypted") != "true":
                    raise ValueError(f"Unexpected encryption profile: {source.name}")
                encrypted = next(
                    (node for node in root if node.tag.rsplit("}", 1)[-1] == "encryptedData"), None
                )
                if encrypted is None:
                    raise ValueError(f"Encrypted definition has no content: {source.name}")
                cms = base64.b64decode("".join((encrypted.text or "").split()), validate=True)
                compressed = run(
                    [
                        openssl,
                        "cms",
                        "-decrypt",
                        "-binary",
                        "-inform",
                        "DER",
                        "-inkey",
                        str(key),
                        "-recip",
                        str(certificate),
                    ],
                    cms,
                )
                with gzip.GzipFile(fileobj=io.BytesIO(compressed)) as stream:
                    decoded = stream.read(MAX_XML + 1)
                if len(decoded) > MAX_XML:
                    raise ValueError(f"Definition exceeds the decoded XML bound: {source.name}")
                parsed = ET.fromstring(decoded)
                if parsed.attrib.get("isEncrypted") != "false":
                    raise ValueError(
                        f"Decoded definition did not clear encryption flag: {source.name}"
                    )
                identifier = next(
                    (
                        node
                        for node in parsed.iter()
                        if node.tag.rsplit("}", 1)[-1] in {"cafIdent", "fpIdent", "sweIdent"}
                    ),
                    None,
                )
                if identifier is None:
                    raise ValueError(f"Definition has no source identity: {source.name}")
                fields = {node.tag.rsplit("}", 1)[-1]: node.text for node in identifier}
                name = f"{fields['id']}-{fields['mainVersion']}-{fields['subVersion']}-{fields['patchVersion']}"
                if not re.fullmatch(r"[0-9A-F]{8}-[0-9]{3}-[0-9]{3}-[0-9]{3}", name):
                    raise ValueError(f"Definition identity is not canonical: {source.name}")
                relative = f"{kind}/{name}.xml.gz"
                if relative in manifest["documents"]:
                    raise ValueError(f"Duplicate source definition identity: {name}")
                target = output / relative
                target.parent.mkdir(exist_ok=True)
                packed = gzip.compress(decoded, mtime=0)
                temp = target.with_suffix(".tmp")
                temp.write_bytes(packed)
                os.replace(temp, target)
                manifest["documents"][relative] = {
                    "kind": kind,
                    "identifier": name,
                    "source_filename": source.name,
                    "source_sha256": digest(raw),
                    "xml_sha256": digest(decoded),
                    "gzip_sha256": digest(packed),
                    "xml_bytes": len(decoded),
                }
                if len(manifest["documents"]) % 250 == 0:
                    print(f"Decoded {len(manifest['documents'])} source definitions", flush=True)
    encoded = (json.dumps(manifest, sort_keys=True, indent=2) + "\n").encode()
    temporary = output / ".manifest.tmp"
    temporary.write_bytes(encoded)
    os.replace(temporary, output / "manifest.json")
    return {"documents": len(manifest["documents"]), "manifest_sha256": digest(encoded)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("psdz", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--openssl", default="/opt/homebrew/bin/openssl")
    parser.add_argument("--include-fafp", action="store_true")
    args = parser.parse_args()
    print(
        json.dumps(
            recover(args.psdz, args.output, openssl=args.openssl, include_fafp=args.include_fafp),
            indent=2,
        )
    )
