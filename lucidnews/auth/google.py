"""Sign in with Google: OAuth 2.0 authorization code flow with PKCE, as an OpenID Connect client.

Protections, each required by the standards and checked on return:

- ``state``: random, single use, bound to the browser that started the flow by a cookie, so a
  callback forged by someone else is refused (login CSRF);
- PKCE (``S256``): the code is useless without the verifier kept here;
- ``nonce``: must come back inside the ID token;
- the ID token comes straight from Google's token endpoint over TLS, in answer to a request
  authenticated with the client secret. OpenID Connect Core 3.1.3.7 allows trusting it without
  checking its signature in that case; ``iss``, ``aud``, ``exp``, ``nonce`` and
  ``email_verified`` are still checked.
"""

import base64
import hashlib
import json
import secrets
import threading
import time
from dataclasses import dataclass
from typing import Callable, Dict, Optional, Tuple
from urllib.parse import urlencode

import httpx

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
ISSUERS = ("https://accounts.google.com", "accounts.google.com")
FLOW_TTL = 600  # seconds the reader has to finish at Google
MAX_PENDING = 1000


class GoogleError(Exception):
    """The flow cannot continue. ``code`` is safe to show; nothing from Google is echoed."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class GoogleProfile:
    sub: str
    email: str
    name: str
    picture: Optional[str]


@dataclass
class _Pending:
    binder_hash: str
    verifier: str
    nonce: str
    next_path: str
    expires: float


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def decode_claims(id_token: str) -> Dict[str, object]:
    try:
        payload = id_token.split(".")[1]
        return json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
    except (IndexError, ValueError):
        raise GoogleError("invalid_token") from None


class GoogleOAuth:
    def __init__(
        self,
        client_id: str,
        client_secret: str,
        *,
        auth_url: str = GOOGLE_AUTH_URL,
        token_url: str = GOOGLE_TOKEN_URL,
        timeout: float = 10.0,
        clock: Callable[[], float] = time.time,
    ):
        self.client_id = client_id
        self._client_secret = client_secret
        self.auth_url = auth_url
        self.token_url = token_url
        self.timeout = timeout
        self._clock = clock
        self._pending: Dict[str, _Pending] = {}
        self._lock = threading.Lock()

    def begin(self, redirect_uri: str, next_path: str) -> Tuple[str, str]:
        """(URL to send the browser to, binder to keep in a cookie)."""
        state, binder = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        verifier, nonce = secrets.token_urlsafe(48), secrets.token_urlsafe(24)
        now = self._clock()
        with self._lock:
            self._pending = {key: flow for key, flow in self._pending.items() if flow.expires > now}
            if len(self._pending) >= MAX_PENDING:
                raise GoogleError("busy")
            self._pending[state] = _Pending(_sha256(binder), verifier, nonce, next_path, now + FLOW_TTL)
        query = urlencode(
            {
                "client_id": self.client_id,
                "redirect_uri": redirect_uri,
                "response_type": "code",
                "scope": "openid email profile",
                "state": state,
                "nonce": nonce,
                "code_challenge": _b64url(hashlib.sha256(verifier.encode("ascii")).digest()),
                "code_challenge_method": "S256",
                "prompt": "select_account",
            }
        )
        return f"{self.auth_url}?{query}", binder

    def cancel(self, state: str) -> None:
        with self._lock:
            self._pending.pop(state, None)

    def complete(self, code: str, state: str, binder: Optional[str], redirect_uri: str) -> Tuple[GoogleProfile, str]:
        """Check the return, exchange the code, validate the ID token. ``(profile, next_path)``."""
        with self._lock:
            flow = self._pending.pop(state, None)  # single use, whatever happens next
        if flow is None or flow.expires <= self._clock():
            raise GoogleError("state_invalid")
        if not binder or not secrets.compare_digest(_sha256(binder), flow.binder_hash):
            raise GoogleError("state_invalid")
        try:
            response = httpx.post(
                self.token_url,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": redirect_uri,
                    "client_id": self.client_id,
                    "client_secret": self._client_secret,
                    "code_verifier": flow.verifier,
                },
                headers={"Accept": "application/json"},
                timeout=self.timeout,
            )
            payload = response.json() if response.status_code == 200 else None
        except (httpx.HTTPError, ValueError):
            raise GoogleError("token_exchange_failed") from None
        if not isinstance(payload, dict) or not isinstance(payload.get("id_token"), str):
            raise GoogleError("token_exchange_failed")
        claims = decode_claims(payload["id_token"])
        audience = claims.get("aud")
        if claims.get("iss") not in ISSUERS or (audience != self.client_id and not (isinstance(audience, list) and self.client_id in audience)):
            raise GoogleError("invalid_token")
        expires = claims.get("exp")
        if not isinstance(expires, (int, float)) or expires <= self._clock():
            raise GoogleError("invalid_token")
        if not secrets.compare_digest(str(claims.get("nonce") or ""), flow.nonce):
            raise GoogleError("invalid_token")
        email, sub = claims.get("email"), claims.get("sub")
        if not isinstance(email, str) or not isinstance(sub, str) or not email or not sub:
            raise GoogleError("invalid_token")
        if claims.get("email_verified") is not True:
            raise GoogleError("email_not_verified")
        name = claims.get("name") if isinstance(claims.get("name"), str) else ""
        picture = claims.get("picture") if isinstance(claims.get("picture"), str) and str(claims.get("picture")).startswith("https://") else None
        return GoogleProfile(sub=sub, email=email.strip().lower(), name=name.strip(), picture=picture), flow.next_path
