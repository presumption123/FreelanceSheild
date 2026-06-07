"""AES-256-GCM encryption for OAuth tokens at rest."""

import os
from binascii import hexlify, unhexlify

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.config import get_settings

ALGORITHM = "aes-256-gcm"


def _get_key() -> bytes:
    return unhexlify(get_settings().encryption_key[:64])


def encrypt(plaintext: str) -> str:
    iv = os.urandom(12)
    aesgcm = AESGCM(_get_key())
    encrypted = aesgcm.encrypt(iv, plaintext.encode("utf-8"), None)
    ciphertext, auth_tag = encrypted[:-16], encrypted[-16:]
    return f"{hexlify(iv).decode()}:{hexlify(auth_tag).decode()}:{hexlify(ciphertext).decode()}"


def decrypt(ciphertext: str) -> str:
    iv_hex, auth_tag_hex, data_hex = ciphertext.split(":")
    iv = unhexlify(iv_hex)
    auth_tag = unhexlify(auth_tag_hex)
    data = unhexlify(data_hex)
    aesgcm = AESGCM(_get_key())
    return aesgcm.decrypt(iv, data + auth_tag, None).decode("utf-8")
