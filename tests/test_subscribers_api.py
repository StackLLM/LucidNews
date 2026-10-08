import http.client
import json
import threading
from http.server import ThreadingHTTPServer

import pytest

from src.archive import ItemArchive
from src.newsletter.store import SubscriberStore
from src.subscribers_api import SubscriberService, source_options, subscriber_id
from src.web_api import ApiContext, is_loopback, make_handler, resolve, resolve_write

CONFIGURED = {
    "rss/LWN.net": "rss",
    "github/astral-sh/uv": "github",
    "github/@torvalds": "github",
    "reddit/r/devops": "reddit",
    "hackernews": "hackernews",
}


@pytest.fixture
def ctx(tmp_path) -> ApiContext:
    store = SubscriberStore(tmp_path / "subscribers.json")
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

    stored = SubscriberStore(tmp_path / "subscribers.json").get("ada@example.com")
    assert stored.preferences.min_importance.value == "high"
    assert [s["email"] for s in resolve(ctx, "/api/subscribers", {})[1]["subscribers"]] == ["Ada@Example.com"]

    assert resolve_write(ctx, "DELETE", f"/api/subscribers/{created['id']}", {}) == (200, {"deleted": created["id"]})
    assert SubscriberStore(tmp_path / "subscribers.json").load() == []
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
