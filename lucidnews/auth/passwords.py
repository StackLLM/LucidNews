"""Password hashing with scrypt (standard library): salted, memory-hard, constant-time compare."""

import base64
import hashlib
import hmac
import secrets

MIN_LENGTH = 8
MAX_LENGTH = 128  # bounds the work an attacker can force per request
_N, _R, _P = 2**14, 8, 1
_DKLEN = 32


def _derive(password: str, salt: bytes, n: int, r: int, p: int) -> bytes:
    return hashlib.scrypt(password.encode("utf-8"), salt=salt, n=n, r=r, p=p, dklen=_DKLEN, maxmem=64 * 1024 * 1024)


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = _derive(password, salt, _N, _R, _P)
    b64 = lambda raw: base64.b64encode(raw).decode("ascii")  # noqa: E731
    return f"scrypt${_N}${_R}${_P}${b64(salt)}${b64(digest)}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, n, r, p, salt, digest = stored.split("$")
        if scheme != "scrypt":
            return False
        expected = base64.b64decode(digest)
        actual = _derive(password, base64.b64decode(salt), int(n), int(r), int(p))
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(actual, expected)


# Verified when the e-mail is unknown, so a sign-in takes the same time either way.
DUMMY_HASH = hash_password(secrets.token_urlsafe(16))


def password_problem(password: object) -> str | None:
    """None when acceptable, else a short machine-readable reason."""
    if not isinstance(password, str):
        return "required"
    if len(password) < MIN_LENGTH:
        return "too_short"
    if len(password) > MAX_LENGTH:
        return "too_long"
    return None
