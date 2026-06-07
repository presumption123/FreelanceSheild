"""HMAC-signed portal tokens for client-facing URLs."""

import base64
import hmac
import hashlib
import time

from app.config import get_settings

TOKEN_TTL_MS = 90 * 24 * 60 * 60 * 1000


def generate_portal_token(invoice_id: str) -> str:
    secret = get_settings().portal_hmac_secret.encode()
    timestamp = str(int(time.time() * 1000))
    payload = f"{invoice_id}.{timestamp}"
    sig = hmac.new(secret, payload.encode(), hashlib.sha256).hexdigest()
    token_bytes = f"{payload}.{sig}".encode()
    return base64.urlsafe_b64encode(token_bytes).decode().rstrip("=")


def verify_portal_token(token: str, invoice_id: str) -> bool:
    try:
        padding = "=" * (-len(token) % 4)
        decoded = base64.urlsafe_b64decode(token + padding).decode("utf-8")
        parts = decoded.split(".")
        if len(parts) != 3:
            return False
        token_invoice_id, timestamp, sig = parts
        if token_invoice_id != invoice_id:
            return False
        if int(time.time() * 1000) - int(timestamp) > TOKEN_TTL_MS:
            return False
        secret = get_settings().portal_hmac_secret.encode()
        expected = hmac.new(secret, f"{token_invoice_id}.{timestamp}".encode(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(sig, expected)
    except Exception:
        return False
