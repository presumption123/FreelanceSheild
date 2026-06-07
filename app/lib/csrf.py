"""CSRF double-submit token helpers."""

import hashlib
import hmac
import secrets

from app.config import get_settings


def generate_csrf_token(session_id: str) -> str:
    nonce = secrets.token_hex(16)
    sig = hmac.new(
        get_settings().session_secret.encode(),
        f"{session_id}.{nonce}".encode(),
        hashlib.sha256,
    ).hexdigest()
    return f"{nonce}.{sig}"


def validate_csrf_token(token: str, session_id: str) -> bool:
    parts = token.split(".")
    if len(parts) != 2:
        return False
    nonce, sig = parts
    expected = hmac.new(
        get_settings().session_secret.encode(),
        f"{session_id}.{nonce}".encode(),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(sig, expected)
