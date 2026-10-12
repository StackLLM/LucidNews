"""The public service (``lucidnews-public``): confirmation and unsubscription links only.

Deliberately separate from ``lucidnews-api``, which stays on localhost. This process serves
four routes and nothing else: no archive, no subscriber list, no preferences, no settings.

- ``GET /confirm?t=<token>`` and ``GET /unsubscribe?t=<token>`` show a page with a button.
  They change nothing: mail scanners and link previewers open links, and must not confirm
  or unsubscribe anyone.
- ``POST /confirm?t=`` confirms a pending subscriber.
- ``POST /unsubscribe?t=`` unsubscribes (also the RFC 8058 one-click request that mail
  clients send for the ``List-Unsubscribe-Post`` header).
- ``GET /health``.

Tokens are signed (see ``newsletter.tokens``): a modified, expired or foreign one is refused.
It reads and writes the same ``newsletter.sqlite3`` as the pipeline, so it runs where the
data directory is.
"""

import argparse
import html
import logging
import sys
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable, Dict, List, Optional
from urllib.parse import parse_qs, urlsplit

from ._cli import add_data_dir_arguments
from .newsletter import tokens
from .newsletter.db import SubscriberDB
from .newsletter.models import SubscriptionStatus
from .newsletter.provider import secret

logger = logging.getLogger(__name__)

MAX_BODY_BYTES = 2048

TEXTS: Dict[str, Dict[str, str]] = {
    "en": {
        "confirm_title": "Confirm your subscription",
        "confirm_button": "Confirm my subscription",
        "confirm_done": "Thank you: your subscription is confirmed.",
        "unsubscribe_title": "Unsubscribe",
        "unsubscribe_button": "Unsubscribe me",
        "unsubscribe_done": "You are unsubscribed. You will not receive any more e-mails.",
        "invalid": "This link is not valid or has expired.",
        "unavailable": "This service is not available right now.",
    },
    "fr": {
        "confirm_title": "Confirmez votre inscription",
        "confirm_button": "Confirmer mon inscription",
        "confirm_done": "Merci : votre inscription est confirmée.",
        "unsubscribe_title": "Se désinscrire",
        "unsubscribe_button": "Me désinscrire",
        "unsubscribe_done": "Vous êtes désinscrit(e). Vous ne recevrez plus d’e-mails.",
        "invalid": "Ce lien n’est pas valide ou a expiré.",
        "unavailable": "Ce service n’est pas disponible pour le moment.",
    },
}
CSP = "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'"


def page(language: str, title: str, message: str = "", button: Optional[str] = None, action: Optional[str] = None) -> bytes:
    form = ""
    if button and action:
        form = f'<form method="post" action="{html.escape(action, quote=True)}"><button type="submit">{html.escape(button)}</button></form>'
    body = (
        f'<!DOCTYPE html><html lang="{html.escape(language, quote=True)}"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1"><meta name="robots" content="noindex">'
        f"<title>{html.escape(title)}</title><style>body{{margin:0;padding:48px 16px;background:#f4f5fa;color:#0f1530;"
        "font-family:-apple-system,'Segoe UI',Helvetica,Arial,sans-serif;line-height:1.6}"
        ".card{max-width:480px;margin:0 auto;background:#fff;border-radius:18px;padding:28px 32px;box-shadow:0 1px 3px rgba(15,21,48,.08)}"
        "h1{font-family:Georgia,serif;font-size:24px;margin:0 0 12px}button{background:#4c3fd8;color:#fff;border:0;border-radius:10px;"
        "padding:12px 20px;font-size:15px;font-weight:600;cursor:pointer}</style></head>"
        f'<body><div class="card"><h1>{html.escape(title)}</h1><p>{html.escape(message)}</p>{form}</div></body></html>'
    )
    return body.encode("utf-8")


class PublicService:
    def __init__(self, db: SubscriberDB, signing_key: Optional[str]):
        self.db = db
        self.signing_key = signing_key

    def _texts(self, language: str) -> Dict[str, str]:
        return TEXTS.get(language, TEXTS["en"])

    def show(self, action: str, token: str) -> tuple[int, bytes]:
        """The page behind a link: a button, nothing changed."""
        try:
            claims = tokens.verify(self.signing_key, token, action)
        except tokens.TokenError:
            return HTTPStatus.BAD_REQUEST, page("en", self._texts("en")["invalid"], "")
        texts = self._texts(claims.language)
        return HTTPStatus.OK, page(
            claims.language, texts[f"{action}_title"], "", texts[f"{action}_button"], f"/{action}?t={token}"
        )

    def apply(self, action: str, token: str) -> tuple[int, bytes]:
        try:
            claims = tokens.verify(self.signing_key, token, action)
        except tokens.TokenError:
            return HTTPStatus.BAD_REQUEST, page("en", self._texts("en")["invalid"], "")
        texts = self._texts(claims.language)
        if self.db.get_by_id(claims.subscriber_id) is None:
            if action == tokens.CONFIRM:
                return HTTPStatus.BAD_REQUEST, page(claims.language, texts["invalid"])  # erased: nothing to confirm
            return HTTPStatus.OK, page(claims.language, texts[f"{action}_done"])  # already gone: the outcome holds
        if action == tokens.CONFIRM:
            self.db.confirm(claims.subscriber_id)  # no-op unless pending: a reader who left stays out
            current = self.db.get_by_id(claims.subscriber_id)
            if current is None or current.status is not SubscriptionStatus.CONFIRMED:
                return HTTPStatus.BAD_REQUEST, page(claims.language, texts["invalid"])
        else:
            self.db.unsubscribe(claims.subscriber_id)
        return HTTPStatus.OK, page(claims.language, texts[f"{action}_done"])


def make_handler(service: PublicService) -> type:
    class Handler(BaseHTTPRequestHandler):
        server_version = "LucidNewsPublic"
        sys_version = ""

        def _send(self, status: int, body: bytes, content_type: str = "text/html; charset=utf-8") -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy", CSP)
            self.end_headers()
            self.wfile.write(body)

        def _route(self) -> tuple[str, str]:
            parts = urlsplit(self.path)
            token = (parse_qs(parts.query).get("t") or [""])[0]
            return parts.path.rstrip("/"), token

        def do_GET(self) -> None:  # noqa: N802
            path, token = self._route()
            if path == "/health":
                return self._send(HTTPStatus.OK, b'{"status":"ok"}', "application/json")
            if path in ("/confirm", "/unsubscribe"):
                status, body = service.show(path.lstrip("/"), token)
                return self._send(status, body)
            self._send(HTTPStatus.NOT_FOUND, page("en", "Not found"))

        def do_POST(self) -> None:  # noqa: N802
            path, token = self._route()
            if path not in ("/confirm", "/unsubscribe"):
                return self._send(HTTPStatus.NOT_FOUND, page("en", "Not found"))
            try:
                length = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                length = MAX_BODY_BYTES + 1
            if length > MAX_BODY_BYTES:
                return self._send(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, page("en", "Too large"))
            self.rfile.read(length)  # the token is in the address; the body (form or one-click) is not needed
            status, body = service.apply(path.lstrip("/"), token)
            self._send(status, body)

        def log_message(self, format: str, *args) -> None:  # noqa: A002
            # Never log the query string: it holds the token.
            logger.info("%s %s", self.command, urlsplit(self.path).path)

    return Handler


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="LucidNews public service: confirmation and unsubscription links")
    parser.add_argument("--host", default="127.0.0.1", help="Bind address (default: 127.0.0.1; put a TLS reverse proxy in front)")
    parser.add_argument("--port", type=int, default=8780)
    add_data_dir_arguments(parser)
    args = parser.parse_args(argv)

    from .storage.manager import StorageManager

    storage = StorageManager(data_dir=args.data_dir, config_path=args.config)
    try:
        config = storage.load_config()
    except (OSError, ValueError) as exc:
        print(f"Cannot read the configuration: {type(exc).__name__}", file=sys.stderr)
        return 1
    email = config.email
    key = secret(email.signing_key_env) if email else None
    if not email or not key or len(key) < tokens.MIN_KEY_LENGTH:
        print("Set the signing key (email.signing_key_env, at least 16 characters) first.", file=sys.stderr)
        return 1
    server = ThreadingHTTPServer((args.host, args.port), make_handler(PublicService(storage.subscribers, key)))
    print(f"LucidNews public service on http://{args.host}:{args.port} (confirm, unsubscribe)", file=sys.stderr)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
