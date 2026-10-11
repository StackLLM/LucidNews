"""Lot 22: double opt-in, signed links, delivery log, providers and the public service."""

import http.client
import json
import threading
from datetime import datetime, timezone
from http.server import ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest

from src.models import EmailConfig
from src.newsletter import DigestPreferences, Subscriber, SubscriptionStatus, subscriber_id, tokens
from src.newsletter.build import Newsletter
from src.newsletter.db import SubscriberDB
from src.newsletter.digest import plan_deliveries
from src.newsletter.mailer import Mailer
from src.newsletter.provider import ResendProvider, SendResult, SmtpProvider
from src.newsletter.render import UNSUBSCRIBE_PLACEHOLDER, RenderedEmail, render_email
from src.newsletter.store import SubscriberStore
from src.public_api import PublicService, make_handler

KEY = "k" * 32
BASE = "https://news.example.org"


def email_config(**overrides) -> EmailConfig:
    data = {
        "imap_server": "i",
        "smtp_server": "s",
        "email_address": "news@example.org",
        "enabled": True,
        "public_base_url": BASE,
        "provider": "resend",
    }
    data.update(overrides)
    return EmailConfig(**data)


class FakeProvider:
    name = "resend"

    def __init__(self, fail_for=()):
        self.sent = []
        self.fail_for = set(fail_for)

    def send(self, to, subject, html, text, headers):
        if to in self.fail_for:
            return SendResult(False, error="Resend 422: invalid address")
        self.sent.append({"to": to, "subject": subject, "html": html, "text": text, "headers": dict(headers)})
        return SendResult(True, provider_id=f"id-{len(self.sent)}")


def newsletter() -> Newsletter:
    email = render_email("# Digest\n\nHello", language="en", sender_name="LucidNews", unsubscribe_keyword="UNSUBSCRIBE", unsubscribe_link=True)
    return Newsletter(subject="LucidNews — 2026-10-11", email=email, item_count=1, unanalyzed_count=0)


# --- Signed links -----------------------------------------------------------------------------


def test_a_token_round_trips_and_carries_its_action() -> None:
    token = tokens.sign(KEY, "abc", tokens.CONFIRM, "fr")

    claims = tokens.verify(KEY, token, tokens.CONFIRM)

    assert (claims.subscriber_id, claims.action, claims.language) == ("abc", "confirm", "fr")
    with pytest.raises(tokens.TokenError, match="another action"):
        tokens.verify(KEY, token, tokens.UNSUBSCRIBE)


def test_a_forged_modified_or_foreign_token_is_refused() -> None:
    token = tokens.sign(KEY, "abc", tokens.UNSUBSCRIBE)
    payload, signature = token.split(".")
    forged_payload = tokens._b64(json.dumps({"s": "someone-else", "a": "unsubscribe", "e": None, "l": "en"}).encode())

    for bad in (f"{forged_payload}.{signature}", f"{payload}.{signature[:-2]}AA", payload, "", "a.b.c", "x" * 1000, f"{payload}."):
        with pytest.raises(tokens.TokenError):
            tokens.verify(KEY, bad, tokens.UNSUBSCRIBE)
    with pytest.raises(tokens.TokenError):
        tokens.verify("z" * 32, token, tokens.UNSUBSCRIBE)  # another key
    with pytest.raises(tokens.TokenError, match="signing key"):
        tokens.sign("short", "abc", tokens.CONFIRM)
    with pytest.raises(tokens.TokenError):
        tokens.verify(None, token, tokens.UNSUBSCRIBE)


def test_a_confirmation_link_expires_but_an_unsubscribe_link_never_does() -> None:
    now = 1_000_000.0
    confirm = tokens.sign(KEY, "abc", tokens.CONFIRM, now=now)
    leave = tokens.sign(KEY, "abc", tokens.UNSUBSCRIBE, now=now)

    assert tokens.verify(KEY, confirm, tokens.CONFIRM, now=now + 6 * 24 * 3600).subscriber_id == "abc"
    with pytest.raises(tokens.TokenError, match="expired"):
        tokens.verify(KEY, confirm, tokens.CONFIRM, now=now + 8 * 24 * 3600)
    assert tokens.verify(KEY, leave, tokens.UNSUBSCRIBE, now=now + 10 * 365 * 24 * 3600).subscriber_id == "abc"


# --- Database and migration ----------------------------------------------------------------------


def test_the_json_file_is_imported_once_as_confirmed_and_kept(tmp_path) -> None:
    SubscriberStore(tmp_path / "subscribers.json").save(
        [Subscriber(email="a@example.com", preferences=DigestPreferences(language="fr", detail_level="brief")), Subscriber(email="b@example.com")]
    )

    db = SubscriberDB(tmp_path / "newsletter.sqlite3")

    loaded = db.load()
    assert [s.email for s in loaded] == ["a@example.com", "b@example.com"]
    assert all(s.status is SubscriptionStatus.CONFIRMED for s in loaded)
    assert loaded[0].preferences.language == "fr" and loaded[0].preferences.detail_level.value == "brief"
    assert not (tmp_path / "subscribers.json").exists()
    assert (tmp_path / "subscribers.json.migrated").exists()
    # Opening again imports nothing more, even if a new file appears.
    SubscriberStore(tmp_path / "subscribers.json").save([Subscriber(email="late@example.com")])
    assert len(SubscriberDB(tmp_path / "newsletter.sqlite3").load()) == 2


def test_status_transitions_follow_double_opt_in(tmp_path) -> None:
    db = SubscriberDB(tmp_path / "n.sqlite3")
    pending = Subscriber(email="p@example.com", status=SubscriptionStatus.PENDING)
    assert db.insert(pending) and not db.insert(Subscriber(email="P@Example.com"))  # one row per address

    assert db.confirm(pending.id).status is SubscriptionStatus.CONFIRMED
    assert db.confirm(pending.id).confirmed_at is not None
    left = db.unsubscribe(pending.id)
    assert left.status is SubscriptionStatus.UNSUBSCRIBED and left.unsubscribed_at is not None
    # Confirming an old link does not bring a reader who left back; only a new request does.
    assert db.confirm(pending.id).status is SubscriptionStatus.UNSUBSCRIBED
    assert db.request_again(pending.id).status is SubscriptionStatus.PENDING
    assert db.delete(pending.id) is True and db.get_by_id(pending.id) is None


def test_deleting_a_subscriber_erases_their_delivery_log(tmp_path) -> None:
    db = SubscriberDB(tmp_path / "n.sqlite3")
    sub = db.add("a@example.com")
    db.log_delivery(sub, "daily", "s", ok=True, reference="run-1")

    db.delete(sub.id)

    assert db.deliveries() == []


# --- Nothing before confirmation ------------------------------------------------------------------


def test_pending_and_unsubscribed_readers_are_never_planned_or_sent_a_digest(tmp_path) -> None:
    db = SubscriberDB(tmp_path / "n.sqlite3")
    db.insert(Subscriber(email="ok@example.com"))
    db.insert(Subscriber(email="pending@example.com", status=SubscriptionStatus.PENDING))
    db.insert(Subscriber(email="gone@example.com", status=SubscriptionStatus.UNSUBSCRIBED))

    plan = plan_deliveries(db.load(), [], ["en"])
    assert sorted(plan.not_confirmed) == ["gone@example.com", "pending@example.com"]
    assert [d.recipients for d in plan.deliveries] == [["ok@example.com"]]

    # Even a stale plan cannot send to them: the mailer looks each address up again.
    provider = FakeProvider()
    summary = Mailer(email_config(), db, provider, KEY).send_digest(
        newsletter(), ["ok@example.com", "pending@example.com", "gone@example.com", "unknown@example.com"], "daily", "run-1"
    )
    assert [m["to"] for m in provider.sent] == ["ok@example.com"]
    assert (summary.sent, summary.failed, summary.skipped) == (1, 0, 3)


def test_each_digest_carries_its_readers_own_signed_unsubscribe_link(tmp_path) -> None:
    db = SubscriberDB(tmp_path / "n.sqlite3")
    a, b = db.add("a@example.com"), db.add("b@example.com")
    provider = FakeProvider()

    Mailer(email_config(), db, provider, KEY).send_digest(newsletter(), ["a@example.com", "b@example.com"], "daily", "run-1")

    for message, sub in zip(provider.sent, (a, b)):
        url = message["headers"]["List-Unsubscribe"].strip("<>")
        assert url.startswith(f"{BASE}/unsubscribe?t=")
        token = parse_qs(urlsplit(url).query)["t"][0]
        assert tokens.verify(KEY, token, tokens.UNSUBSCRIBE).subscriber_id == sub.id
        assert message["headers"]["List-Unsubscribe-Post"] == "List-Unsubscribe=One-Click"
        assert UNSUBSCRIBE_PLACEHOLDER not in message["html"] + message["text"] and url in message["text"]
    assert provider.sent[0]["headers"]["List-Unsubscribe"] != provider.sent[1]["headers"]["List-Unsubscribe"]


def test_with_resend_a_digest_without_a_link_is_refused_and_logged(tmp_path) -> None:
    db = SubscriberDB(tmp_path / "n.sqlite3")
    db.add("a@example.com")
    provider = FakeProvider()

    summary = Mailer(email_config(public_base_url=None), db, provider, KEY).send_digest(newsletter(), ["a@example.com"], "daily", "run-1")

    assert provider.sent == [] and summary.failed == 1
    assert "no unsubscribe link" in db.deliveries()[0].error


# --- Confirmation and delivery log ----------------------------------------------------------------


def test_a_confirmation_request_is_sent_logged_and_only_for_pending_readers(tmp_path) -> None:
    db = SubscriberDB(tmp_path / "n.sqlite3")
    db.insert(Subscriber(email="p@example.com", status=SubscriptionStatus.PENDING, preferences=DigestPreferences(language="fr")))
    db.insert(Subscriber(email="c@example.com"))
    provider = FakeProvider()
    mailer = Mailer(email_config(), db, provider, KEY)

    assert mailer.send_confirmation(db.get("p@example.com")).ok
    assert not mailer.send_confirmation(db.get("c@example.com")).ok  # already confirmed

    [message] = provider.sent
    assert message["to"] == "p@example.com" and "Confirmez" in message["subject"] + message["html"]
    url = next(word for word in message["text"].split() if word.startswith(BASE))
    assert tokens.verify(KEY, parse_qs(urlsplit(url).query)["t"][0], tokens.CONFIRM).subscriber_id == subscriber_id("p@example.com")
    assert [(d.kind, d.status) for d in db.deliveries()] == [("confirmation", "failed"), ("confirmation", "sent")]


def test_every_send_is_logged_and_a_failure_does_not_stop_the_others(tmp_path) -> None:
    db = SubscriberDB(tmp_path / "n.sqlite3")
    db.add("bad@example.com")
    good = db.add("good@example.com")
    provider = FakeProvider(fail_for={"bad@example.com"})

    summary = Mailer(email_config(), db, provider, KEY).send_digest(newsletter(), ["bad@example.com", "good@example.com"], "weekly", "2026-10-05")

    assert (summary.sent, summary.failed) == (1, 1)
    log = db.deliveries()
    assert [(d.email, d.kind, d.status, d.reference) for d in log] == [
        ("good@example.com", "weekly", "sent", "2026-10-05"),
        ("bad@example.com", "weekly", "failed", "2026-10-05"),
    ]
    assert log[1].error == "Resend 422: invalid address" and log[0].provider_id == "id-1"
    assert [d.subject for d in db.deliveries(subscriber=good.id)] == ["LucidNews — 2026-10-11"]


def test_a_confirmation_without_links_configured_fails_and_says_why(tmp_path) -> None:
    db = SubscriberDB(tmp_path / "n.sqlite3")
    db.insert(Subscriber(email="p@example.com", status=SubscriptionStatus.PENDING))

    result = Mailer(email_config(public_base_url=None), db, FakeProvider(), KEY).send_confirmation(db.get("p@example.com"))

    assert not result.ok and "public_base_url" in result.error
    assert db.deliveries()[0].status == "failed"


# --- Providers ------------------------------------------------------------------------------------


def resend(handler, key="re_secret_value"):
    return ResendProvider(email_config(), key, httpx.Client(transport=httpx.MockTransport(handler)))


def test_resend_sends_json_with_the_key_in_the_header_only() -> None:
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"], seen["body"], seen["url"] = request.headers["authorization"], json.loads(request.content), str(request.url)
        return httpx.Response(200, json={"id": "abc-123"})

    result = resend(handler).send("a@example.com", "Subject", "<p>x</p>", "x", {"List-Unsubscribe": "<https://x>"})

    assert result == SendResult(True, provider_id="abc-123")
    assert seen["url"] == "https://api.resend.com/emails" and seen["auth"] == "Bearer re_secret_value"
    assert seen["body"]["to"] == ["a@example.com"] and seen["body"]["headers"] == {"List-Unsubscribe": "<https://x>"}
    assert seen["body"]["from"] == "LucidNews Daily <news@example.org>" and "re_secret_value" not in json.dumps(seen["body"])


def test_resend_failures_become_results_without_leaking_the_key() -> None:
    refused = resend(lambda r: httpx.Response(422, json={"message": "The to field is invalid"})).send("a@example.com", "s", "h", "t", {})
    assert not refused.ok and refused.error == "Resend 422: The to field is invalid"

    def boom(request):
        raise httpx.ConnectError("no route", request=request)

    down = resend(boom).send("a@example.com", "s", "h", "t", {})
    assert not down.ok and "unreachable" in down.error and "re_secret_value" not in down.error
    missing = resend(lambda r: httpx.Response(200, json={"id": "x"}), key=None).send("a@example.com", "s", "h", "t", {})
    assert not missing.ok and "RESEND_API_KEY" in missing.error


def test_smtp_provider_sends_headers_and_never_raises(monkeypatch) -> None:
    sent = []

    class Server:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def login(self, user, password):
            sent.append(("login", user, password))

        def send_message(self, message):
            sent.append(("message", message["To"], message["List-Unsubscribe"], message.get_payload()[1].get_content_type()))

    manager = type("M", (), {"config": email_config(provider="smtp"), "pwd": "pw", "_open_smtp": lambda self: Server()})()

    assert SmtpProvider(manager).send("a@example.com", "s", "<p>h</p>", "t", {"List-Unsubscribe": "<https://x>"}).ok
    assert sent[1] == ("message", "a@example.com", "<https://x>", "text/html")

    def broken():
        raise OSError("down")

    manager._open_smtp = broken
    assert SmtpProvider(manager).send("a@example.com", "s", "h", "t", {}).error == "SMTP: OSError"


# --- Public service -------------------------------------------------------------------------------


@pytest.fixture
def public(tmp_path):
    db = SubscriberDB(tmp_path / "n.sqlite3")
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(PublicService(db, KEY)))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield db, server.server_address[1]
    server.shutdown()
    server.server_close()


def call(port, method, target, body=b""):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    conn.request(method, target, body=body, headers={"Content-Type": "application/x-www-form-urlencoded"})
    response = conn.getresponse()
    data = response.read().decode()
    headers = {k.lower(): v for k, v in response.getheaders()}
    conn.close()
    return response.status, data, headers


def test_opening_a_link_changes_nothing_and_the_button_does(public) -> None:
    db, port = public
    sub = Subscriber(email="p@example.com", status=SubscriptionStatus.PENDING, preferences=DigestPreferences(language="fr"))
    db.insert(sub)
    token = tokens.sign(KEY, sub.id, tokens.CONFIRM, "fr")

    status, page, headers = call(port, "GET", f"/confirm?t={token}")
    assert status == 200 and "Confirmer mon inscription" in page and "<form" in page
    assert db.get_by_id(sub.id).status is SubscriptionStatus.PENDING  # a scanner opening the link confirms nothing
    assert headers["cache-control"] == "no-store" and "default-src 'none'" in headers["content-security-policy"]

    status, page, _ = call(port, "POST", f"/confirm?t={token}")
    assert status == 200 and "confirmée" in page
    assert db.get_by_id(sub.id).status is SubscriptionStatus.CONFIRMED


def test_one_click_unsubscribe_and_a_modified_link(public) -> None:
    db, port = public
    sub = db.add("a@example.com")
    token = tokens.sign(KEY, sub.id, tokens.UNSUBSCRIBE)

    tampered = call(port, "POST", f"/unsubscribe?t={token[:-3]}abc", b"List-Unsubscribe=One-Click")
    assert tampered[0] == 400 and db.get_by_id(sub.id).status is SubscriptionStatus.CONFIRMED
    assert call(port, "POST", f"/confirm?t={token}")[0] == 400  # a token for another action

    status, page, _ = call(port, "POST", f"/unsubscribe?t={token}", b"List-Unsubscribe=One-Click")
    assert status == 200 and "unsubscribed" in page
    assert db.get_by_id(sub.id).status is SubscriptionStatus.UNSUBSCRIBED
    assert call(port, "POST", f"/unsubscribe?t={token}")[0] == 200  # twice is fine


def test_an_old_confirmation_does_not_bring_back_a_reader_who_left(public) -> None:
    db, port = public
    sub = db.add("a@example.com")
    db.unsubscribe(sub.id)

    status, _, _ = call(port, "POST", f"/confirm?t={tokens.sign(KEY, sub.id, tokens.CONFIRM)}")

    assert status == 400 and db.get_by_id(sub.id).status is SubscriptionStatus.UNSUBSCRIBED


def test_the_public_service_serves_nothing_else(public) -> None:
    _, port = public
    for target in ("/", "/api/subscribers", "/api/editions/latest", "/api/settings", "/subscribers.json"):
        assert call(port, "GET", target)[0] == 404
    assert call(port, "POST", "/api/subscribers", b"{}")[0] == 404
    assert call(port, "GET", "/health")[0] == 200
    assert call(port, "POST", "/confirm?t=x", b"x" * 5000)[0] == 413
    assert call(port, "GET", "/unsubscribe")[0] == 400


def test_a_link_for_an_erased_reader_confirms_nothing_and_unsubscribes_quietly(public) -> None:
    _, port = public
    ghost = subscriber_id("erased@example.com")

    assert call(port, "POST", f"/confirm?t={tokens.sign(KEY, ghost, tokens.CONFIRM)}")[0] == 400
    assert call(port, "POST", f"/unsubscribe?t={tokens.sign(KEY, ghost, tokens.UNSUBSCRIBE)}")[0] == 200
