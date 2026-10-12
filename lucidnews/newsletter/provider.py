"""How an e-mail leaves: SMTP, or Resend's HTTPS API.

Both return a ``SendResult`` and never raise for a delivery problem, so one bad address
cannot stop the others. Error text never contains the credentials.
"""

import logging
import os
from dataclasses import dataclass
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Dict, Mapping, Optional, Protocol

import httpx

from ..models import EmailConfig

logger = logging.getLogger(__name__)

RESEND_URL = "https://api.resend.com/emails"
TIMEOUT = 20.0


@dataclass(frozen=True)
class SendResult:
    ok: bool
    provider_id: Optional[str] = None
    error: Optional[str] = None


class EmailProvider(Protocol):
    name: str

    def send(self, to: str, subject: str, html: str, text: str, headers: Mapping[str, str]) -> SendResult: ...


def secret(name: str) -> Optional[str]:
    """An environment variable, else the project's ``.env`` (the API process does not load it)."""
    value = os.environ.get(name)
    if value:
        return value
    from dotenv import dotenv_values

    from ..settings_api import PROJECT_ENV_FILE

    try:
        return dotenv_values(PROJECT_ENV_FILE).get(name) or None if PROJECT_ENV_FILE.exists() else None
    except OSError:
        return None


class ResendProvider:
    name = "resend"

    def __init__(self, config: EmailConfig, api_key: Optional[str], client: Optional[httpx.Client] = None):
        self.config = config
        self.api_key = api_key
        self.client = client or httpx.Client(timeout=TIMEOUT)

    def send(self, to: str, subject: str, html: str, text: str, headers: Mapping[str, str]) -> SendResult:
        if not self.api_key:
            return SendResult(False, error=f"{self.config.resend_api_key_env} is not set")
        payload: Dict[str, object] = {
            "from": f"{self.config.sender_name} <{self.config.email_address}>",
            "to": [to],
            "subject": subject,
            "html": html,
            "text": text,
        }
        if headers:
            payload["headers"] = dict(headers)
        try:
            response = self.client.post(RESEND_URL, json=payload, headers={"Authorization": f"Bearer {self.api_key}"})
        except httpx.HTTPError as exc:
            return SendResult(False, error=f"Resend unreachable: {type(exc).__name__}")
        try:
            body = response.json()
        except ValueError:
            body = {}
        if response.status_code // 100 == 2 and isinstance(body, dict) and body.get("id"):
            return SendResult(True, provider_id=str(body["id"]))
        message = body.get("message") if isinstance(body, dict) else None
        return SendResult(False, error=f"Resend {response.status_code}: {str(message or 'refused')[:200]}")


class SmtpProvider:
    name = "smtp"

    def __init__(self, manager):
        self.manager = manager  # EmailManager: knows the server and the password

    def send(self, to: str, subject: str, html: str, text: str, headers: Mapping[str, str]) -> SendResult:
        config = self.manager.config
        message = MIMEMultipart("alternative")
        message["Subject"] = subject
        message["From"] = f"{config.sender_name} <{config.email_address}>"
        message["To"] = to
        for name, value in headers.items():
            message[name] = value
        message.attach(MIMEText(text, "plain"))
        message.attach(MIMEText(html, "html"))
        try:
            with self.manager._open_smtp() as server:
                server.login(config.smtp_username or config.email_address, self.manager.pwd)
                server.send_message(message)
        except Exception as exc:  # noqa: BLE001 - any SMTP failure is a delivery failure
            return SendResult(False, error=f"SMTP: {type(exc).__name__}")
        return SendResult(True)
