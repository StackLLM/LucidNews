"""Sources managed from the web app: list, add, edit, enable, remove and test."""

import http.client
import json
import shutil
import threading
from datetime import datetime, timedelta, timezone
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

from lucidnews import sources_api
from lucidnews.archive import ItemArchive
from lucidnews.models import Config, ContentItem, SourceType
from lucidnews.processing import ProfileRegistry
from lucidnews.settings_api import SettingsService
from lucidnews.source_health import configured_source_keys
from lucidnews.sources_api import SourcesService
from lucidnews.url_security import UnsafeURLError, validate_http_url
from lucidnews.web_api import build_context, make_handler, resolve

ROOT = Path(__file__).resolve().parents[1]
PROFILES = ProfileRegistry.load(ROOT / "profiles", "tech-news")
FEED_TOKEN = "feed-token-value-1234"
INTERNAL = ("10.0.0.1", "intranet.example")


async def fake_resolve_public(url: str) -> str:
    """url_security without DNS: two hosts stand for internal addresses."""
    validate_http_url(url)
    if any(host in url for host in INTERNAL):
        raise UnsafeURLError("Destination resolves to a non-public address: 10.0.0.1")
    return url


@pytest.fixture
def service(tmp_path, monkeypatch) -> SourcesService:
    config = json.loads((ROOT / "data" / "config.example.json").read_text())
    del config["sources"]["google_news"]  # a section absent from the file
    config["sources"]["rss"].append(
        {"name": "Private feed", "url": "https://example.com/feed?token=${LUCIDNEWS_FEED_TOKEN}", "enabled": True}
    )
    monkeypatch.setenv("LUCIDNEWS_FEED_TOKEN", FEED_TOKEN)
    (tmp_path / "config.json").write_text(json.dumps(config, indent=2))
    changes: list[int] = []
    settings = SettingsService(
        config_path=tmp_path / "config.json",
        backup_dir=tmp_path / "backups",
        profiles=PROFILES,
        env_path=tmp_path / ".env",
        on_change=lambda: changes.append(1),
    )
    service = SourcesService(settings, resolve_public=fake_resolve_public)
    service.changes = changes  # type: ignore[attr-defined]
    return service


def raw(service: SourcesService) -> dict:
    return json.loads(service.settings.config_path.read_text())


def config(service: SourcesService) -> Config:
    return service.settings.snapshot()[2]


def listing(service: SourcesService) -> dict:
    status, body = service.list()
    assert status == 200
    return body


def entry(service: SourcesService, key: str) -> dict:
    return next(source for source in listing(service)["sources"] if source["key"] == key)


# Listing -----------------------------------------------------------------------------


def test_list_reports_every_source_with_the_health_key(service) -> None:
    body = listing(service)
    by_key = {source["key"]: source for source in body["sources"]}

    assert by_key["rss/OpenAI News"]["values"] == {"name": "OpenAI News", "url": "https://openai.com/news/rss.xml"}
    assert by_key["github/vllm-project/vllm"]["values"] == {"repository": "vllm-project/vllm"}
    assert by_key["reddit/r/LocalLLaMA"]["group_enabled"] is False  # Reddit is switched off
    assert by_key["hackernews"]["removable"] is False
    assert by_key["google_news"]["configured"] is False and by_key["google_news"]["enabled"] is False
    assert by_key["twitter"]["readonly"] is True and by_key["twitter"]["values"] == {}
    assert by_key["twitter"]["summary"] == {"mode": "apify", "users": 2, "keywords": 0}
    # Every source a run collects is listed under the same key as its health.
    enabled = {source["key"] for source in body["sources"] if source["enabled"] and not source["group"]}
    assert set(configured_source_keys(config(service))) <= enabled | {"reddit", "telegram"}


def test_a_placeholder_is_shown_as_written_and_locks_the_source(service) -> None:
    private = entry(service, "rss/Private feed")

    assert private["locked"] is True
    assert private["values"]["url"] == "https://example.com/feed?token=${LUCIDNEWS_FEED_TOKEN}"
    assert FEED_TOKEN not in json.dumps(listing(service))


# Add ---------------------------------------------------------------------------------


def test_add_writes_the_source_and_reports_its_key(service) -> None:
    version = listing(service)["version"]

    status, body = service.add(
        {"version": version, "kind": "rss", "values": {"name": " Fresh feed ", "url": "https://feeds.example.org/new.xml"}}
    )

    assert status == 201, body
    assert body["key"] == "rss/Fresh feed"
    assert raw(service)["sources"]["rss"][-1] == {"name": "Fresh feed", "url": "https://feeds.example.org/new.xml", "enabled": True}
    assert "rss/Fresh feed" in configured_source_keys(config(service))  # collected by the next run
    assert service.changes == [1]
    assert len(list(service.settings.backup_dir.iterdir())) == 1


@pytest.mark.parametrize(
    "kind, values, stored",
    [
        ("github_repo", {"repository": "https://github.com/pallets/flask"},
         {"type": "repo_releases", "owner": "pallets", "repo": "flask", "enabled": True}),
        ("github_user", {"username": "@gvanrossum"}, {"type": "user_events", "username": "gvanrossum", "enabled": True}),
        ("reddit_subreddit", {"subreddit": "r/rust", "fetch_limit": 10},
         {"subreddit": "rust", "fetch_limit": 10, "enabled": True}),
        ("telegram_channel", {"channel": "https://t.me/s/durov"}, {"channel": "durov", "enabled": True}),
    ],
)
def test_add_accepts_pasted_links_and_prefixes(service, kind, values, stored) -> None:
    status, body = service.add({"version": listing(service)["version"], "kind": kind, "values": values})

    assert status == 201, body
    sources = raw(service)["sources"]
    container = {
        "github_repo": sources["github"], "github_user": sources["github"],
        "reddit_subreddit": sources["reddit"]["subreddits"], "telegram_channel": sources["telegram"]["channels"],
    }[kind]
    assert container[-1] == stored


@pytest.mark.parametrize(
    "values, field",
    [
        ({"name": "openai news", "url": "https://example.org/other.xml"}, "name"),  # same key, other case
        ({"name": "Copy", "url": "https://openai.com/news/rss.xml/"}, "url"),  # same feed
    ],
)
def test_duplicates_are_refused(service, values, field) -> None:
    before = raw(service)

    status, body = service.add({"version": listing(service)["version"], "kind": "rss", "values": values})

    assert status == 409 and field in body["fields"]
    assert raw(service) == before


@pytest.mark.parametrize(
    "kind, values, field",
    [
        ("rss", {"name": "Internal", "url": "http://10.0.0.1/feed"}, "url"),
        ("rss", {"name": "Intranet", "url": "https://intranet.example/rss"}, "url"),
        ("rss", {"name": "Local", "url": "http://localhost:8080/rss"}, "url"),
        ("rss", {"name": "Files", "url": "file:///etc/passwd"}, "url"),
        ("rss", {"name": "Secret", "url": "https://example.com/?k=${OPENAI_API_KEY}"}, "url"),
        ("rss", {"name": "No URL"}, "url"),
        ("github_repo", {"repository": "not a repo"}, "repository"),
        ("reddit_subreddit", {"subreddit": "a"}, "subreddit"),
        ("reddit_subreddit", {"subreddit": "rust", "fetch_limit": 1000}, "fetch_limit"),
        ("rss", {"name": "X", "url": "https://example.com/x", "trust": "official"}, "trust"),  # not editable here
    ],
)
def test_invalid_or_internal_sources_are_refused(service, kind, values, field) -> None:
    before = raw(service)

    status, body = service.add({"version": listing(service)["version"], "kind": kind, "values": values})

    assert status == 422 and field in body["fields"], body
    assert raw(service) == before
    assert service.changes == []


def test_a_stale_version_is_refused(service) -> None:
    status, _ = service.add({"version": "old", "kind": "rss", "values": {"name": "A", "url": "https://a.example/rss"}})

    assert status == 409


# Edit, enable, remove ---------------------------------------------------------------


def test_disable_and_enable_change_what_the_run_collects(service) -> None:
    status, _ = service.update("rss/OpenAI News", {"version": listing(service)["version"], "values": {"enabled": False}})
    assert status == 200
    assert "rss/OpenAI News" not in configured_source_keys(config(service))
    assert entry(service, "rss/OpenAI News")["enabled"] is False

    service.update("rss/OpenAI News", {"version": listing(service)["version"], "values": {"enabled": True}})
    assert "rss/OpenAI News" in configured_source_keys(config(service))


def test_edit_renames_and_keeps_the_other_fields(service) -> None:
    status, body = service.update(
        "rss/OpenAI News", {"version": listing(service)["version"], "values": {"name": "OpenAI"}}
    )

    assert status == 200 and body["key"] == "rss/OpenAI"
    stored = raw(service)["sources"]["rss"][0]
    assert stored["name"] == "OpenAI" and stored["category"] == "ai" and stored["profile"] == "tech-news"


def test_edit_to_an_existing_name_is_refused(service) -> None:
    status, body = service.update(
        "rss/OpenAI News", {"version": listing(service)["version"], "values": {"name": "Google DeepMind"}}
    )

    assert status == 409 and "name" in body["fields"]


def test_a_section_absent_from_the_file_is_created_when_enabled(service) -> None:
    status, _ = service.update("google_news", {"version": listing(service)["version"], "values": {"enabled": True}})

    assert status == 200
    assert raw(service)["sources"]["google_news"] == {"enabled": True}
    assert "google_news" in configured_source_keys(config(service))


def test_settings_of_built_in_sources_are_edited(service) -> None:
    version = listing(service)["version"]

    status, body = service.update(
        "hackernews", {"version": version, "values": {"min_score": 150, "fetch_top_stories": 40}}
    )

    assert status == 200, body
    assert raw(service)["sources"]["hackernews"] == {
        "enabled": True, "fetch_top_stories": 40, "min_score": 150, "profile": "auto",
    }


def test_unchanged_values_leave_the_file_alone(service) -> None:
    before = service.settings.config_path.read_text()
    current = entry(service, "rss/OpenAI News")

    status, _ = service.update("rss/OpenAI News", {"version": listing(service)["version"], "values": current["values"]})

    assert status == 200
    assert service.settings.config_path.read_text() == before
    assert service.changes == []


def test_a_locked_source_can_be_switched_but_not_edited(service) -> None:
    version = listing(service)["version"]

    status, body = service.update("rss/Private feed", {"version": version, "values": {"url": "https://example.com/x"}})
    assert status == 422 and "url" in body["fields"]

    status, _ = service.update("rss/Private feed", {"version": version, "values": {"enabled": False}})
    assert status == 200
    stored = raw(service)["sources"]["rss"][-1]
    assert stored == {"name": "Private feed", "url": "https://example.com/feed?token=${LUCIDNEWS_FEED_TOKEN}", "enabled": False}


def test_x_is_read_only(service) -> None:
    status, _ = service.update("twitter", {"version": listing(service)["version"], "values": {"enabled": True}})

    assert status == 422


def test_delete_removes_list_sources_only(service) -> None:
    version = listing(service)["version"]

    assert service.delete("rss/OpenAI News", {"version": version})[0] == 200
    assert all(feed["name"] != "OpenAI News" for feed in raw(service)["sources"]["rss"])
    version = listing(service)["version"]
    assert service.delete("hackernews", {"version": version})[0] == 422
    assert service.delete("rss/Nope", {"version": version})[0] == 404


# Test fetch --------------------------------------------------------------------------


def _item(title: str, hours_ago: float) -> ContentItem:
    return ContentItem(
        id=f"rss:test:{title}",
        source_type=SourceType.RSS,
        title=title,
        url="https://example.com/" + title,
        published_at=datetime.now(timezone.utc) - timedelta(hours=hours_ago),
    )


class FakeScraper:
    def __init__(self, items=(), source_errors=None, request_url=None, client=None, warn=None):
        self.items = list(items)
        self.source_errors = source_errors or {}
        self.request_url = request_url
        self.client = client
        self.warn = warn

    async def fetch(self, since):
        if self.warn:
            import logging

            logging.getLogger("lucidnews.scrapers.reddit").warning(self.warn)
        if self.request_url:
            await self.client.get(self.request_url)
        return [item for item in self.items if item.published_at >= since]


def test_a_test_reports_what_the_source_returns(service, monkeypatch) -> None:
    items = [_item("new", 2), _item("old", 50), _item("ancient", 24 * 30)]
    monkeypatch.setattr(sources_api, "_scraper", lambda kind, model, client: FakeScraper(items))

    status, body = service.test({"kind": "rss", "values": {"name": "T", "url": "https://example.com/rss"}})

    assert status == 200
    assert body["ok"] is True and body["count"] == 2 and body["days"] == 7
    assert body["in_window"] == 1 and body["window_hours"] == 24
    assert [entry["title"] for entry in body["sample"]] == ["new", "old"]
    assert raw(service) == raw(service)  # nothing written
    assert service.changes == []


def test_a_failing_source_reports_its_error(service, monkeypatch) -> None:
    monkeypatch.setattr(
        sources_api, "_scraper",
        lambda kind, model, client: FakeScraper(source_errors={"rss/T": "HTTPStatusError: Client error '404 Not Found'"}),
    )

    _, body = service.test({"kind": "rss", "values": {"name": "T", "url": "https://example.com/rss"}})

    assert body["ok"] is False and "404" in body["error"]


def test_a_logged_failure_is_reported_when_nothing_came_back(service, monkeypatch) -> None:
    monkeypatch.setattr(
        sources_api, "_scraper", lambda kind, model, client: FakeScraper(warn="Reddit request failed: 403 Blocked")
    )

    _, body = service.test({"kind": "reddit_subreddit", "values": {"subreddit": "rust"}})

    assert body["ok"] is False and body["error"] == "Reddit request failed: 403 Blocked"


def test_a_test_never_reaches_an_internal_address(service, monkeypatch) -> None:
    # A public feed that redirects (or links) to an internal address.
    monkeypatch.setattr(
        sources_api, "_scraper",
        lambda kind, model, client: FakeScraper(request_url="http://10.0.0.1/admin", client=client),
    )

    _, body = service.test({"kind": "rss", "values": {"name": "T", "url": "https://example.com/rss"}})

    assert body["ok"] is False and "non-public" in body["error"]
    status, body = service.test({"kind": "rss", "values": {"name": "T", "url": "http://10.0.0.1/rss"}})
    assert status == 422


def test_a_saved_source_is_tested_by_key_without_revealing_its_token(service, monkeypatch) -> None:
    seen = {}

    def fake(kind, model, client):
        seen["url"] = str(model.url)
        return FakeScraper(source_errors={"rss/Private feed": f"404 for url {model.url}"})

    monkeypatch.setattr(sources_api, "_scraper", fake)

    _, body = service.test({"key": "rss/Private feed"})

    assert FEED_TOKEN in seen["url"]  # the scraper gets the real URL
    assert FEED_TOKEN not in json.dumps(body)
    assert "${LUCIDNEWS_FEED_TOKEN}" in body["error"]


def test_x_and_groups_cannot_be_tested(service) -> None:
    assert service.test({"key": "twitter"})[0] == 422
    assert service.test({"kind": "reddit"})[0] == 400


# HTTP ---------------------------------------------------------------------------------


@pytest.fixture
def api(tmp_path, monkeypatch):
    shutil.copy(ROOT / "data" / "config.example.json", tmp_path / "config.json")
    ItemArchive(tmp_path / "archive.sqlite3")
    monkeypatch.chdir(ROOT)
    ctx = build_context(str(tmp_path), None, local_features=True)
    ctx.sources.resolve_public = fake_resolve_public
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(ctx))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield ctx, server.server_address[1]
    server.shutdown()
    server.server_close()


def _request(port, method, path, body=None, headers=None):  # type: ignore[no-untyped-def]
    conn = http.client.HTTPConnection("127.0.0.1", port)
    data = json.dumps(body).encode() if body is not None else None
    conn.request(method, path, body=data, headers={"Content-Type": "application/json", **(headers or {})})
    response = conn.getresponse()
    payload = json.loads(response.read() or b"{}")
    conn.close()
    return response.status, payload


def test_http_source_routes_are_local_and_update_the_health_view(api) -> None:
    ctx, port = api
    local = {"Origin": "http://localhost:5173"}

    status, body = _request(port, "GET", "/api/sources/config")
    assert status == 200
    assert _request(port, "GET", "/api/sources/config", headers={"Host": "evil.example"})[0] == 403
    assert _request(port, "POST", "/api/sources/test", {"key": "hackernews"}, {"Origin": "https://evil.example"})[0] == 403

    status, body = _request(port, "POST", "/api/sources/config",
                            {"version": body["version"], "kind": "rss",
                             "values": {"name": "Fresh feed", "url": "https://feeds.example.org/new.xml"}}, local)
    assert status == 201, body
    assert "rss/Fresh feed" in ctx.configured_sources  # the health view now expects it

    key = "/api/sources/config/" + "rss%2FFresh%20feed"
    status, body = _request(port, "PUT", key, {"version": body["version"], "values": {"enabled": False}}, local)
    assert status == 200 and "rss/Fresh feed" not in ctx.configured_sources
    status, _ = _request(port, "DELETE", key, {"version": body["version"]}, local)
    assert status == 200


def test_source_routes_are_absent_without_local_features(tmp_path, monkeypatch) -> None:
    shutil.copy(ROOT / "data" / "config.example.json", tmp_path / "config.json")
    ItemArchive(tmp_path / "archive.sqlite3")
    monkeypatch.chdir(ROOT)
    ctx = build_context(str(tmp_path), None, local_features=False)

    assert resolve(ctx, "/api/sources/config", {})[0] == 403
    assert resolve(ctx, "/api/sources", {})[0] == 200  # the public health view stays


def test_test_titles_are_shown_decoded(service, monkeypatch) -> None:
    monkeypatch.setattr(sources_api, "_scraper", lambda kind, model, client: FakeScraper([_item("CVE&#x27;s fixed", 1)]))

    _, body = service.test({"kind": "rss", "values": {"name": "T", "url": "https://example.com/rss"}})

    assert body["sample"][0]["title"] == "CVE's fixed"
