"""Password hashing with Argon2id."""

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

_hasher = PasswordHasher(
    memory_cost=19456,
    time_cost=2,
    parallelism=1,
    hash_len=32,
)


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except VerifyMismatchError:
        return False


async def check_password_breached(password: str) -> bool:
    """Check HaveIBeenPwned k-anonymity API. Returns True if password appears in breaches."""
    import hashlib

    import httpx

    sha1 = hashlib.sha1(password.encode("utf-8")).hexdigest().upper()
    prefix, suffix = sha1[:5], sha1[5:]
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"https://api.pwnedpasswords.com/range/{prefix}")
            response.raise_for_status()
            return any(line.split(":")[0] == suffix for line in response.text.splitlines())
    except Exception:
        return False
