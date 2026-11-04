"""Derive source-supported coding authorization and block signatures, without I/O."""

import base64
import hashlib
import re

from Crypto.IO import PKCS8
from Crypto.Util.asn1 import DerSequence


def _material(entry: dict) -> bytes:
    """Decode bounded private-key material from the selected source entry."""
    material = entry.get("keyString")
    if not isinstance(material, str) or len(material) > 32768:
        raise ValueError("Coding key material is missing or too large")
    encoded = material.replace("-----BEGIN PRIVATE KEY-----", "").replace(
        "-----END PRIVATE KEY-----", ""
    )
    try:
        return base64.b64decode("".join(encoded.split()), validate=True)
    except ValueError as error:
        raise ValueError("Coding key encoding is invalid") from error


def _rsa_signature(payload: bytes, entry: dict) -> bytes:
    """Encode the source digest, raw RSA signature and word ordering."""
    name = entry.get("digest")
    if not isinstance(name, str):
        raise ValueError("Coding digest selector is missing")
    name = name.lower()
    # The source falls back to MD5 for every other name, including unknown names.
    if name not in {"sha256", "sha512", "sha1"}:
        name = "md5"
    try:
        oid, private_der, _ = PKCS8.unwrap(_material(entry))
        sequence = DerSequence().decode(private_der, strict=True)
        if oid != "1.2.840.113549.1.1.1" or len(sequence) != 9 or sequence[0] != 0:
            raise ValueError("Unsupported coding private-key structure")
        modulus, _, private_exponent = sequence[1:4]
        if (
            not isinstance(modulus, int)
            or not isinstance(private_exponent, int)
            or modulus <= 0
            or private_exponent <= 0
        ):
            raise ValueError("Coding RSA exponents are incomplete")
    except (ValueError, IndexError, TypeError) as error:
        raise ValueError("Coding RSA key is invalid") from error
    # Some supplied PKCS8 entries omit CRT values (p/q are zero). The source
    # uses only RSAPrivateKey modulus/private exponent, so do not require CRT.
    if modulus % 2 != 1 or not 0 < private_exponent < modulus:
        raise ValueError("Coding RSA parameters are invalid")
    if modulus.bit_length() % 8:
        raise ValueError("Coding RSA modulus is not byte aligned")
    width = modulus.bit_length() // 8
    if not 64 <= width <= 1024 or width % 4:
        raise ValueError("Coding modulus width is unsupported")
    digest = hashlib.new(name, payload).digest()
    padded = digest.ljust(width, b"\x00")
    message = int.from_bytes(padded[::-1], "big")
    if message >= modulus:
        raise ValueError("Coding message exceeds the key modulus")
    signature = pow(message, private_exponent, modulus).to_bytes(width, "big")
    return (width // 4).to_bytes(4, "big") + b"".join(
        signature[offset : offset + 4] for offset in range(width - 4, -1, -4)
    )


def derive_authorization_key(seed: bytes, entry: dict) -> bytes:
    """Encode an exact AS challenge bound to its recovered bootloader entry.

    This helper neither probes keys nor authorizes a write. Callers bind the
    selected entry to fresh vehicle identity before sending its result.
    """
    identifier = entry.get("bootloaderID")
    if not isinstance(identifier, str) or not re.fullmatch(r"[0-9A-F]{8}", identifier):
        raise ValueError("Authorization bootloader identifier is invalid")
    if entry.get("keyType") != 0 or entry.get("algorithm") != 0:
        raise ValueError("Unsupported coding authorization algorithm")
    if not isinstance(seed, bytes) or not 0 < len(seed) <= 4096:
        raise ValueError("Authorization seed is missing or too large")
    return _rsa_signature(b"\xff\xff\xff\xff" + bytes.fromhex(identifier) + seed, entry)


def sign_coding_data(payload: bytes, entry: dict) -> bytes:
    """Sign concatenated source-defined coding groups using an exact NCDS entry."""
    if entry.get("keyType") != 1:
        raise ValueError("Coding signature requires the matching signing entry")
    if not isinstance(payload, bytes) or not 0 < len(payload) <= 16 * 1024 * 1024:
        raise ValueError("Coding signature input is missing or too large")
    if entry.get("algorithm") == 0:
        return _rsa_signature(payload, entry)
    if entry.get("algorithm") == 1:
        # The source names this algorithm DES but implements an MD5 sandwich.
        key = _material(entry)
        return hashlib.md5(key + payload + key).digest()
    raise ValueError("Unsupported coding signature algorithm")
