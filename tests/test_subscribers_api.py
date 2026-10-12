import http.client
import json
import threading
from http.server import ThreadingHTTPServer

import pytest

from lucidnews.archive import ItemArchive
from lucidnews.newsletter.db import SubscriberDB
from lucidnews.subscribers_api import SubscriberService, source_options, subscriber_id
from lucidnews.web_api import ApiContext, is_loopback, make_handler, resolve, resolve_write

CONFIGURED = {
    "rss/LWN.net": "rss",
    "github/astral-sh/uv": "github",
    "github/@torvalds": "github",
    "reddit/r/devops": "reddit",
    "hackernews": "hackernews",
}


@pytest.fixture
def ctx(tmp_path) -> ApiContext:
    store = SubscriberDB(tmp_path / "newsletter.sqlite3")
    return ApiContext(
        archive=ItemArchive(tmp_path / "archive.sqlite3"),
        subscribers=SubscriberService(store, ["en", "fr"], CONFIGURED),
    )


def test_options_list_languages_categories_and_filterable_sources(ctx) -> None:
    status, body = resolve(ctx, "/api/preferences/options", {})

    assert status == 200
    assert [language["code"] for language in body["languages"]] == ["en", "fr"]
    assert "cybersecurity" in body["categories"]
    assert body["importance_levels"] == ["low", "medium", "high", "critical"]
    assert {plan["id"] for plan in body["plans"]} == {"free", "premium"}
    # GitHub user feeds cannot be filtered on (items carry the repo), so they are not offered.
    assert [(o["value"], o["kind"]) for o in body["sources"]] == [
        ("github", "type"),
        ("hackernews", "type"),
        ("reddit", "type"),
        ("rss", "type"),
        ("astral-sh/uv", "source"),
        ("devops", "source"),
        ("LWN.net", "source"),
    ]
    assert source_options({}) == []


def test_create_update_delete_round_trip(ctx, tmp_path) -> None:
    status, created = resolve_write(ctx, "POST", "/api/subscribers", {"email": "Ada@Example.com"})
    assert status == 201
    assert created["id"] == subscriber_id("ada@example.com")
    assert created["preferences"]["language"] == "en"
    assert created["plan"] == "free"

    assert resolve_write(ctx, "POST", "/api/subscribers", {"email": "ada@example.com"})[0] == 409

    preferences = {
        "language": "fr",
        "categories": ["security", "ai"],  # alias normalized
        "sources": ["LWN.net"],
        "frequency": "weekly",
        "min_importance": "high",
        "include_unconfirmed": False,
        "max_items": 8,
    }
    status, updated = resolve_write(ctx, "PUT", f"/api/subscribers/{created['id']}", {"preferences": preferences})
    assert status == 200
    assert updated["preferences"]["categories"] == ["cybersecurity", "ai"]
    assert updated["preferences"]["include_unconfirmed"] is False

    stored = SubscriberDB(tmp_path / "newsletter.sqlite3").get("ada@example.com")
    assert stored.preferences.min_importance.value == "high"
    assert [s["email"] for s in resolve(ctx, "/api/subscribers", {})[1]["subscribers"]] == ["Ada@Example.com"]

    assert resolve_write(ctx, "DELETE", f"/api/subscribers/{created['id']}", {}) == (200, {"deleted": created["id"]})
    assert SubscriberDB(tmp_path / "newsletter.sqlite3").load() == []
    assert resolve_write(ctx, "DELETE", f"/api/subscribers/{created['id']}", {})[0] == 404


@pytest.mark.parametrize(
    ("body", "field"),
    [
        ({"preferences": {"categories": ["gardening"]}}, "categories"),
        ({"preferences": {"max_items": 0}}, "max_items"),
        ({"preferences": {"language": "zh"}}, "language"),  # supported, but not produced here
        ({"preferences": {"unknown": 1}}, "unknown"),
    ],
)
def test_invalid_preferences_return_field_errors(ctx, body, field) -> None:
    sub_id = resolve_write(ctx, "POST", "/api/subscribers", {"email": "ada@example.com"})[1]["id"]

    status, response = resolve_write(ctx, "PUT", f"/api/subscribers/{sub_id}", body)

    assert status == 422
    assert field in response["fields"]


def test_bad_email_and_ids_are_rejected(ctx) -> None:
    assert "email" in resolve_write(ctx, "POST", "/api/subscribers", {"email": "not-an-email"})[1]["fields"]
    assert resolve_write(ctx, "PUT", "/api/subscribers/../../x", {})[0] == 400
    assert resolve_write(ctx, "PUT", "/api/subscribers/0123456789abcdef", {"preferences": {}})[0] == 404
    assert resolve_write(ctx, "PATCH", "/api/subscribers", {})[0] == 405


def test_subscriber_routes_are_off_when_not_bound_to_loopback(tmp_path) -> None:
    ctx = ApiContext(archive=ItemArchive(tmp_path / "archive.sqlite3"))

    assert resolve(ctx, "/api/subscribers", {})[0] == 403
    assert resolve_write(ctx, "POST", "/api/subscribers", {"email": "ada@example.com"})[0] == 403
    assert is_loopback("127.0.0.1") and is_loopback("::1") and is_loopback("localhost")
    assert not is_loopback("0.0.0.0") and not is_loopback("192.168.1.10")


def _request(port: int, method: str, path: str, body=None, headers=None):
    conn = http.client.HTTPConnection("127.0.0.1", port)
    data = json.dumps(body).encode() if body is not None else None
    conn.request(method, path, body=data, headers=headers or {})
    response = conn.getresponse()
    payload = json.loads(response.read() or b"{}")
    conn.close()
    return response.status, payload


def test_http_guards_block_cross_site_and_rebinding(ctx) -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(ctx))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    port = server.server_address[1]
    json_headers = {"Content-Type": "application/json"}
    try:
        # Same machine, via the Vite proxy: allowed.
        status, _ = _request(port, "POST", "/api/subscribers", {"email": "ada@example.com"},
                             {**json_headers, "Origin": "http://localhost:5173"})
        assert status == 201
        # Another website posting to the local API.
        status, _ = _request(port, "POST", "/api/subscribers", {"email": "eve@example.com"},
                             {**json_headers, "Origin": "https://evil.example"})
        assert status == 403
        # DNS rebinding: a foreign Host name pointing at 127.0.0.1.
        assert _request(port, "GET", "/api/subscribers", headers={"Host": "evil.example"})[0] == 403
        # Form posts (no JSON) are refused.
        status, _ = _request(port, "POST", "/api/subscribers", {"email": "eve@example.com"},
                             {"Content-Type": "text/plain"})
        assert status == 415
        assert [s["email"] for s in _request(port, "GET", "/api/subscribers")[1]["subscribers"]] == ["ada@example.com"]
    finally:
        server.shutdown()
        server.server_close()


# --- Lot 22: double opt-in through the web app ---------------------------------------------------


class FakeMailer:
    def __init__(self, ok=True):
        self.ok = ok
        self.confirmations = []

    def send_confirmation(self, subscriber):
        from lucidnews.newsletter.provider import SendResult

        self.confirmations.append(subscriber.email)
        return SendResult(self.ok, error=None if self.ok else "Resend 422: invalid address")


def _ctx_with_mailer(tmp_path, mailer):
    db = SubscriberDB(tmp_path / "newsletter.sqlite3")
    return ApiContext(
        archive=ItemArchive(tmp_path / "archive.sqlite3"),
        subscribers=SubscriberService(db, ["en", "fr"], CONFIGURED, mailer=lambda: mailer),
    ), db


def test_a_new_reader_is_pending_and_gets_the_confirmation_link(tmp_path) -> None:
    mailer = FakeMailer()
    ctx, db = _ctx_with_mailer(tmp_path, mailer)

    status, body = resolve_write(ctx, "POST", "/api/subscribers", {"email": "new@example.com"})

    assert status == 201 and body["status"] == "pending" and body["confirmed_at"] is None
    assert body["confirmation"] == {"sent": True, "error": None} and mailer.confirmations == ["new@example.com"]
    assert db.get("new@example.com").status.value == "pending"


def test_a_failed_confirmation_is_reported_and_can_be_sent_again(tmp_path) -> None:
    mailer = FakeMailer(ok=False)
    ctx, db = _ctx_with_mailer(tmp_path, mailer)
    sub_id = resolve_write(ctx, "POST", "/api/subscribers", {"email": "new@example.com"})[1]["id"]

    status, body = resolve_write(ctx, "POST", f"/api/subscribers/{sub_id}/confirmation", {})
    assert status == 200 and body["confirmation"]["sent"] is False and "422" in body["confirmation"]["error"]
    assert mailer.confirmations == ["new@example.com"] * 2

    db.confirm(sub_id)
    assert resolve_write(ctx, "POST", f"/api/subscribers/{sub_id}/confirmation", {})[0] == 409  # nothing to confirm
    assert resolve_write(ctx, "POST", f"/api/subscribers/{'0' * 16}/confirmation", {})[0] == 404
    assert resolve_write(ctx, "POST", "/api/subscribers/zz/confirmation", {})[0] == 400


def test_without_a_mailer_the_reader_stays_pending_and_the_reason_is_shown(tmp_path) -> None:
    ctx, _ = _ctx_with_mailer(tmp_path, None)

    body = resolve_write(ctx, "POST", "/api/subscribers", {"email": "new@example.com"})[1]

    assert body["status"] == "pending" and body["confirmation"]["sent"] is False and "email.enabled" in body["confirmation"]["error"]


def test_a_reader_who_left_can_ask_to_come_back_but_only_by_confirming(tmp_path) -> None:
    mailer = FakeMailer()
    ctx, db = _ctx_with_mailer(tmp_path, mailer)
    sub = db.add("gone@example.com")
    db.unsubscribe(sub.id)

    status, body = resolve_write(ctx, "POST", f"/api/subscribers/{sub.id}/confirmation", {})

    assert status == 200 and body["status"] == "pending" and mailer.confirmations == ["gone@example.com"]


def test_the_delivery_log_is_listed_per_reader_and_overall(tmp_path) -> None:
    ctx, db = _ctx_with_mailer(tmp_path, None)
    a, b = db.add("a@example.com"), db.add("b@example.com")
    db.log_delivery(a, "daily", "Subject A", ok=True, reference="run-1")
    db.log_delivery(b, "weekly", "Subject B", ok=False, reference="2026-10-05", error="Resend 422")

    status, body = resolve(ctx, "/api/deliveries", {})
    assert status == 200 and [d["email"] for d in body["deliveries"]] == ["b@example.com", "a@example.com"]
    assert body["deliveries"][0]["status"] == "failed" and body["deliveries"][0]["error"] == "Resend 422"
    assert "provider_id" not in body["deliveries"][0]
    only_a = resolve(ctx, f"/api/subscribers/{a.id}/deliveries", {"limit": ["1"]})[1]["deliveries"]
    assert [d["subject"] for d in only_a] == ["Subject A"]
    assert resolve(ctx, f"/api/subscribers/{'0' * 16}/deliveries", {})[0] == 404
    assert resolve(ctx, "/api/deliveries", {"limit": ["0"]})[0] == 400
    # Local only, like the other subscriber routes.
    assert resolve(ApiContext(archive=ctx.archive), "/api/deliveries", {})[0] == 403
