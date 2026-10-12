"""Signed links for confirmation and unsubscription.

A token is ``<payload>.<signature>``: the payload is URL-safe base64 JSON
``{"s": subscriber id, "a": action, "e": expiry or null, "l": language}`` and the
signature an HMAC-SHA256 of it with a secret only the sender knows. Nothing is stored:
a modified, expired or foreign token is refused, whatever the address.
"""

import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from typing import Optional

CONFIRM = "confirm"
UNSUBSCRIBE = "unsubscribe"
ACTIONS = (CONFIRM, UNSUBSCRIBE)
# A confirmation link lives a week. An unsubscription link never expires: leaving must stay possible.
LIFETIMES = {CONFIRM: 7 * 24 * 3600, UNSUBSCRIBE: None}
MIN_KEY_LENGTH = 16
MAX_TOKEN_LENGTH = 512


class TokenError(ValueError):
    """The token is malformed, forged, expired or not for this action."""


@dataclass(frozen=True)
class Claims:
    subscriber_id: str
    action: str
    language: str


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _signature(key: str, payload: str) -> str:
    return _b64(hmac.new(key.encode("utf-8"), payload.encode("ascii"), hashlib.sha256).digest())


def _check_key(key: Optional[str]) -> str:
    if not key or len(key) < MIN_KEY_LENGTH:
        raise TokenError(f"signing key missing or shorter than {MIN_KEY_LENGTH} characters")
    return key


def sign(key: Optional[str], subscriber_id: str, action: str, language: str = "en", *, now: Optional[float] = None) -> str:
    key = _check_key(key)
    if action not in ACTIONS:
        raise TokenError(f"unknown action: {action}")
    lifetime = LIFETIMES[action]
    expiry = int((time.time() if now is None else now) + lifetime) if lifetime else None
    payload = _b64(json.dumps({"s": subscriber_id, "a": action, "e": expiry, "l": language}, separators=(",", ":")).encode("utf-8"))
    return f"{payload}.{_signature(key, payload)}"


def verify(key: Optional[str], token: str, action: str, *, now: Optional[float] = None) -> Claims:
    """The claims of a valid token for ``action``, else ``TokenError``."""
    key = _check_key(key)
    if not isinstance(token, str) or len(token) > MAX_TOKEN_LENGTH or token.count(".") != 1:
        raise TokenError("malformed token")
    payload, signature = token.split(".")
    if not hmac.compare_digest(signature, _signature(key, payload)):
        raise TokenError("bad signature")
    try:
        data = json.loads(_unb64(payload))
        subscriber, claimed, expiry, language = data["s"], data["a"], data["e"], str(data.get("l") or "en")
    except (ValueError, KeyError, TypeError):
        raise TokenError("malformed token") from None
    if claimed != action:
        raise TokenError("token is for another action")
    if expiry is not None and (time.time() if now is None else now) > expiry:
        raise TokenError("token expired")
    if not isinstance(subscriber, str):
        raise TokenError("malformed token")
    return Claims(subscriber, claimed, language)
