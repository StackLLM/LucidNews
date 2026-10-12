"""Email service for handling subscriptions and sending summaries."""

import email
import imaplib
import logging
import os
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import parseaddr
from typing import List

from rich.console import Console

from ..models import EmailConfig
from ..newsletter.render import RenderedEmail, render_email

logger = logging.getLogger(__name__)


class EmailManager:
    """Manages email subscriptions and sending summaries."""

    def __init__(self, config: EmailConfig, console=None):
        self.config = config
        self.pwd = os.getenv(self.config.password_env)
        self.console = console if console is not None else Console(stderr=True)

        if not self.pwd and self.config.enabled:
            logger.warning(
                f"Environment variable {self.config.password_env} not set. Email features may fail."
            )
            self.console.print(
                f"[yellow]Warning: Environment variable {self.config.password_env} not set. Email features may fail.[/yellow]"
            )

    def check_subscriptions(self, storage_manager, mailer=None):
        """Checks the inbox for subscribe/unsubscribe requests.

        A request to subscribe only creates a *pending* subscriber and sends them the
        confirmation link (``mailer``): nothing else is sent before they confirm.
        """
        if not self.config.enabled or not self.config.imap_enabled:
            return

        try:
            mail = imaplib.IMAP4_SSL(self.config.imap_server, self.config.imap_port)
            mail.login(self.config.email_address, self.pwd)
            mail.select("INBOX")

            keyword = self.config.subscribe_keyword
            search_crit = f'(UNSEEN SUBJECT "{keyword}")'

            status, messages = mail.search(None, search_crit)

            if status == "OK" and messages[0]:
                email_ids = messages[0].split()
                subscribers = storage_manager.load_subscribers()

                for e_id in email_ids:
                    _, msg_data = mail.fetch(e_id, "(RFC822)")
                    for response_part in msg_data:
                        if isinstance(response_part, tuple):
                            msg = email.message_from_bytes(response_part[1])

                            subject = str(msg.get("Subject") or "").strip()
                            if subject.upper() != keyword.upper():
                                continue

                            sender = msg.get("From")

                            if sender:
                                _, email_addr = parseaddr(sender)
                                if email_addr and "@" in email_addr:
                                    if (
                                        "noreply" in email_addr.lower()
                                        or "no-reply" in email_addr.lower()
                                    ):
                                        continue

                                    self._request_subscription(storage_manager, mailer, email_addr)

            unsub_keyword = self.config.unsubscribe_keyword
            search_crit_unsub = f'(UNSEEN SUBJECT "{unsub_keyword}")'

            status, messages = mail.search(None, search_crit_unsub)

            if status == "OK" and messages[0]:
                email_ids = messages[0].split()
                subscribers = storage_manager.load_subscribers()

                for e_id in email_ids:
                    _, msg_data = mail.fetch(e_id, "(RFC822)")
                    for response_part in msg_data:
                        if isinstance(response_part, tuple):
                            msg = email.message_from_bytes(response_part[1])

                            subject = str(msg.get("Subject") or "").strip()
                            if subject.upper() != unsub_keyword.upper():
                                continue

                            sender = msg.get("From")

                            if sender:
                                _, email_addr = parseaddr(sender)
                                if email_addr and "@" in email_addr:
                                    if (
                                        "noreply" in email_addr.lower()
                                        or "no-reply" in email_addr.lower()
                                    ):
                                        continue

                                    self._request_unsubscription(storage_manager, email_addr)

            mail.close()
            mail.logout()

        except Exception as e:
            logger.error(f"Error checking subscriptions: {e}")

    @staticmethod
    def _request_subscription(storage_manager, mailer, email_addr: str) -> None:
        from ..newsletter.models import Subscriber, SubscriptionStatus

        db = storage_manager.subscribers
        existing = db.get(email_addr)
        if existing is None:
            if not db.insert(Subscriber(email=email_addr, status=SubscriptionStatus.PENDING)):
                return
            subscriber = db.get(email_addr)
        elif existing.status is SubscriptionStatus.UNSUBSCRIBED:
            subscriber = db.request_again(existing.id)
        elif existing.status is SubscriptionStatus.PENDING:
            subscriber = existing  # asked twice: the link is sent again
        else:
            logger.info("Already subscribed: %s", existing.id)
            return
        logger.info("Subscription requested: %s (pending)", subscriber.id)
        if mailer is not None:
            mailer.send_confirmation(subscriber)

    @staticmethod
    def _request_unsubscription(storage_manager, email_addr: str) -> None:
        db = storage_manager.subscribers
        existing = db.get(email_addr)
        if existing is None:
            logger.info("Not subscribed: %s", email_addr)
            return
        db.unsubscribe(existing.id)
        logger.info("Unsubscribed: %s", existing.id)

    def _open_smtp(self) -> smtplib.SMTP:
        """Open an implicit TLS or STARTTLS SMTP connection."""
        context = ssl.create_default_context()
        if self.config.smtp_port == 465:
            return smtplib.SMTP_SSL(
                self.config.smtp_server, self.config.smtp_port, context=context
            )

        server = smtplib.SMTP(self.config.smtp_server, self.config.smtp_port)
        try:
            server.ehlo()
            server.starttls(context=context)
            server.ehlo()
        except Exception:
            server.close()
            raise
        return server

    def send_daily_summary(
        self, summary_md: str, subject: str, subscribers: List[str], language: str = "en"
    ):
        """Render a Markdown digest (same renderer as the web preview) and send it."""
        rendered = render_email(
            summary_md,
            language=language,
            sender_name=self.config.sender_name,
            unsubscribe_keyword=self.config.unsubscribe_keyword,
        )
        self.send_rendered(rendered, subject, subscribers)

    def send_rendered(self, rendered: RenderedEmail, subject: str, subscribers: List[str]):
        """Send an already rendered e-mail (text + HTML) to each subscriber."""
        if not self.config.enabled or not subscribers:
            return

        try:
            with self._open_smtp() as server:
                server.login(
                    self.config.smtp_username or self.config.email_address, self.pwd
                )

                for subscriber in subscribers:
                    msg = MIMEMultipart("alternative")
                    msg["Subject"] = subject
                    msg["From"] = (
                        f"{self.config.sender_name} <{self.config.email_address}>"
                    )
                    msg["To"] = subscriber
                    msg.attach(MIMEText(rendered.text, "plain"))
                    msg.attach(MIMEText(rendered.html, "html"))

                    try:
                        server.send_message(msg)
                        logger.info(f"Sent summary to {subscriber}")
                    except Exception as e:
                        logger.error(f"Failed to send to {subscriber}: {e}")

        except Exception as e:
            logger.error(f"SMTP Error: {e}")

    def _send_reply(self, to_email: str, subject: str, body: str):
        """Helper to send a simple reply."""
        try:
            with self._open_smtp() as server:
                server.login(
                    self.config.smtp_username or self.config.email_address, self.pwd
                )

                msg = MIMEText(body)
                msg["Subject"] = subject
                msg["From"] = f"{self.config.sender_name} <{self.config.email_address}>"
                msg["To"] = to_email

                server.send_message(msg)
        except Exception as e:
            logger.error(f"Failed to send reply to {to_email}: {e}")
