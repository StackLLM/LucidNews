"""Send newsletters and confirmation requests, and log every attempt.

Rules enforced here, whatever called it:

- only a **confirmed** subscriber is sent a digest (checked again against the database);
- a digest carries the reader's own signed unsubscribe link and the one-click
  ``List-Unsubscribe`` headers; with Resend, a digest without that link is refused;
- every attempt, sent or failed, is logged (who, when, which edition, result).
"""

import html
import logging
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional
from urllib.parse import quote

from ..i18n import BRAND, messages
from ..models import EmailConfig
from . import tokens
from .build import Newsletter
from .db import SubscriberDB
from .models import Subscriber, SubscriptionStatus
from .provider import EmailProvider, SendResult
from .render import UNSUBSCRIBE_PLACEHOLDER

logger = logging.getLogger(__name__)


@dataclass
class SendSummary:
    sent: int = 0
    failed: int = 0
    skipped: int = 0  # not confirmed (any more)


class Mailer:
    def __init__(self, config: EmailConfig, db: SubscriberDB, provider: EmailProvider, signing_key: Optional[str]):
        self.config = config
        self.db = db
        self.provider = provider
        self.signing_key = signing_key

    # Links ------------------------------------------------------------------------------------

    @property
    def links_enabled(self) -> bool:
        return bool(self.config.public_base_url and self.signing_key and len(self.signing_key) >= tokens.MIN_KEY_LENGTH)

    def link(self, subscriber: Subscriber, action: str) -> Optional[str]:
        if not self.links_enabled:
            return None
        token = tokens.sign(self.signing_key, subscriber.id, action, subscriber.preferences.language)
        return f"{self.config.public_base_url}/{action}?t={quote(token, safe='')}"

    # Confirmation -------------------------------------------------------------------------------

    def send_confirmation(self, subscriber: Subscriber) -> SendResult:
        """Ask a pending subscriber to confirm. Nothing else is sent to them before they do."""
        labels = messages(subscriber.preferences.language)
        subject = labels["confirm_subject"]
        url = self.link(subscriber, tokens.CONFIRM)
        if subscriber.status is not SubscriptionStatus.PENDING:
            result = SendResult(False, error="subscriber is not waiting for confirmation")
        elif url is None:
            result = SendResult(False, error="links unavailable: set email.public_base_url and the signing key")
        else:
            body = labels["confirm_body"].format(brand=BRAND)
            safe_url = html.escape(url, quote=True)
            page = (
                f'<!DOCTYPE html><html><body style="font-family:-apple-system,Segoe UI,Helvetica,Arial,sans-serif;'
                f'color:#0f1530;max-width:560px;margin:24px auto;padding:0 16px;line-height:1.6">'
                f"<h1 style=\"font-size:22px\">{html.escape(labels['confirm_title'])}</h1><p>{html.escape(body)}</p>"
                f'<p><a href="{safe_url}" style="display:inline-block;background:#4c3fd8;color:#fff;'
                f'padding:12px 20px;border-radius:10px;text-decoration:none;font-weight:600">'
                f"{html.escape(labels['confirm_button'])}</a></p>"
                f"<p style=\"color:#5b6478;font-size:13px\">{html.escape(labels['confirm_expiry'])}</p></body></html>"
            )
            text = f"{labels['confirm_title']}\n\n{body}\n\n{url}\n\n{labels['confirm_expiry']}\n"
            result = self.provider.send(subscriber.email, subject, page, text, {})
        self.db.log_delivery(subscriber, "confirmation", subject, ok=result.ok, error=result.error, provider_id=result.provider_id)
        return result

    # Digests --------------------------------------------------------------------------------------

    def send_digest(
        self, newsletter: Newsletter, recipients: Iterable[str], kind: str, reference: Optional[str]
    ) -> SendSummary:
        """``recipients``: e-mail addresses; each is looked up again so a reader who left, or never
        confirmed, gets nothing even if the plan was made before."""
        summary = SendSummary()
        for address in recipients:
            current = self.db.get(address)
            if current is None or current.status is not SubscriptionStatus.CONFIRMED:
                summary.skipped += 1
                continue
            url = self.link(current, tokens.UNSUBSCRIBE)
            if url is None and self.provider.name == "resend":
                result = SendResult(False, error="no unsubscribe link: set email.public_base_url and the signing key")
            else:
                headers: Dict[str, str] = {}
                page, text = newsletter.email.html, newsletter.email.text
                if url:
                    headers = {"List-Unsubscribe": f"<{url}>", "List-Unsubscribe-Post": "List-Unsubscribe=One-Click"}
                    page = page.replace(UNSUBSCRIBE_PLACEHOLDER, html.escape(url, quote=True))
                    text = text.replace(UNSUBSCRIBE_PLACEHOLDER, url)
                result = self.provider.send(current.email, newsletter.subject, page, text, headers)
            self.db.log_delivery(
                current, kind, newsletter.subject, ok=result.ok, reference=reference, error=result.error, provider_id=result.provider_id
            )
            if result.ok:
                summary.sent += 1
            else:
                summary.failed += 1
                logger.error("Digest to %s failed: %s", current.id, result.error)
        return summary


def build_mailer(config: EmailConfig, db: SubscriberDB, console=None) -> Mailer:
    """The mailer for this configuration (reads the keys from the environment or ``.env``)."""
    from .provider import ResendProvider, SmtpProvider, secret

    if config.provider == "resend":
        provider: EmailProvider = ResendProvider(config, secret(config.resend_api_key_env))
    else:
        from ..services.email import EmailManager

        provider = SmtpProvider(EmailManager(config, console=console))
    return Mailer(config, db, provider, secret(config.signing_key_env))
