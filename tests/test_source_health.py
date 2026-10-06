import asyncio
import json
from datetime import datetime, timedelta, timezone
from io import StringIO
from types import SimpleNamespace

import httpx
from rich.console import Console

from src.archive import ItemArchive
from src.models import Config, ContentItem, RSSSourceConfig, SourceType
from src.orchestrator import FetchReport, PipelineOrchestrator, SourceFetchOutcome
from src.scrapers.rss import RSSScraper
from src.source_health import (
    HealthStatus,
    SourceRunOutcome,
    assess_health,
    build_source_outcomes,
    configured_source_keys,
    source_key,
)
from src.sources_cli import main as sources_main

NOW = datetime(2026, 10, 6, 12, 0, tzinfo=timezone.utc)


def item(source_type: SourceType, **metadata) -> ContentItem:
    return ContentItem(
        id=f"{source_type.value}:{len(metadata)}:{id(metadata)}",
        source_type=source_type,
        title="t",
        url="https://example.com/x",
        author=metadata.pop("author", None),
        published_at=NOW,
        metadata=metadata,
    )


def test_source_keys_identify_the_configured_sub_source() -> None:
    assert source_key(item(SourceType.RSS, feed_name="LWN.net")) == "rss/LWN.net"
    assert source_key(item(SourceType.GITHUB, repo="vllm-project/vllm", tag="v1")) == "github/vllm-project/vllm"
    assert (
        source_key(item(SourceType.GITHUB, repo="x/y", event_type="PushEvent", author="torvalds"))
        == "github/@torvalds"
    )
    assert source_key(item(SourceType.REDDIT, subreddit="devops")) == "reddit/r/devops"
    assert source_key(item(SourceType.TELEGRAM, channel="news")) == "telegram/@news"
    assert source_key(item(SourceType.HACKERNEWS, author="someone")) == "hackernews"


def test_configured_source_keys_cover_enabled_entries_only() -> None:
    config = Config.model_validate(
        {
            "ai": {"provider": "openai", "model": "m", "api_key_env": "K"},
            "sources": {
                "rss": [
                    {"name": "On", "url": "https://a.example/feed"},
                    {"name": "Off", "url": "https://b.example/feed", "enabled": False},
                ],
                "github": [
                    {"type": "repo_releases", "owner": "astral-sh", "repo": "uv"},
                    {"type": "user_events", "username": "torvalds"},
                ],
                "hackernews": {"enabled": False},
                "reddit": {"enabled": True, "subreddits": [{"subreddit": "devops"}]},
                "gdelt": {"enabled": True},
            },
        }
    )

    assert configured_source_keys(config) == {
        "rss/On": "rss",
        "github/astral-sh/uv": "github",
        "github/@torvalds": "github",
        "reddit/r/devops": "reddit",
        "gdelt": "gdelt",
    }


def test_build_source_outcomes_marks_success_empty_and_failures() -> None:
    configured = {"rss/A": "rss", "rss/B": "rss", "rss/C": "rss", "hackernews": "hackernews"}
    fetched = [item(SourceType.RSS, feed_name="A"), item(SourceType.RSS, feed_name="A")]
    outcomes = build_source_outcomes(
        configured,
        fetched,
        fetched[:1],
        {"rss/C": "HTTPStatusError: 404"},
        {"hackernews": "TimeoutError: slow"},
    )

    by_key = {outcome.source_key: outcome for outcome in outcomes}
    assert (by_key["rss/A"].status, by_key["rss/A"].fetched_count, by_key["rss/A"].selected_count) == ("success", 2, 1)
    assert by_key["rss/B"].status == "empty"
    assert (by_key["rss/C"].status, by_key["rss/C"].error) == ("failure", "HTTPStatusError: 404")
    assert (by_key["hackernews"].status, by_key["hackernews"].error) == ("failure", "TimeoutError: slow")


def rows(key: str, statuses: list[str], fetched: int = 0, selected: int = 0) -> list[dict]:
    return [
        {
            "source_key": key,
            "source_type": key.split("/")[0],
            "status": status,
            "fetched_count": fetched if status == "success" else 0,
            "selected_count": selected if status == "success" else 0,
            "error": "boom" if status == "failure" else None,
            "started_at": (NOW - timedelta(days=index)).isoformat(),
        }
        for index, status in enumerate(statuses)  # newest first
    ]


def test_assess_health_classifies_sources_worst_first() -> None:
    report = assess_health(
        rows("rss/ok", ["success"] * 5, fetched=5, selected=1)
        + rows("rss/dead", ["failure", "failure", "failure", "success"], fetched=3)
        + rows("rss/flaky", ["success", "failure", "success", "failure"], fetched=2)
        + rows("rss/silent", ["empty"] * 5)
        + rows("rss/noisy", ["success"] * 3, fetched=20, selected=0)
        + rows("rss/recovered", ["success", "failure", "failure", "failure", "success", "success"], fetched=4, selected=1)
    )

    status = {health.source_key: health.status for health in report}
    assert status == {
        "rss/dead": HealthStatus.DEAD,
        "rss/flaky": HealthStatus.FAILING,
        "rss/silent": HealthStatus.SILENT,
        "rss/noisy": HealthStatus.NOISY,
        "rss/ok": HealthStatus.HEALTHY,
        "rss/recovered": HealthStatus.FAILING,
    }
    assert report[0].source_key == "rss/dead"
    dead = report[0]
    assert (dead.consecutive_failures, dead.last_error) == (3, "boom")
    assert dead.last_success_at == (NOW - timedelta(days=3)).isoformat()


def test_rss_scraper_reports_failing_feeds_individually() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if "broken" in str(request.url):
            return httpx.Response(404, request=request)
        return httpx.Response(200, text="<rss><channel></channel></rss>", request=request)

    async def run() -> RSSScraper:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            scraper = RSSScraper(
                [
                    RSSSourceConfig(name="Good", url="https://good.example/feed"),
                    RSSSourceConfig(name="Broken", url="https://broken.example/feed"),
                ],
                client,
            )
            await scraper.fetch(NOW - timedelta(days=1))
            return scraper

    scraper = asyncio.run(run())

    assert list(scraper.source_errors) == ["rss/Broken"]
    assert scraper.source_errors["rss/Broken"].startswith("HTTPStatusError: Client error '404")


def test_run_archives_per_source_outcomes_and_warns(tmp_path) -> None:
    archive = ItemArchive(tmp_path / "archive.sqlite3")
    console_output = StringIO()
    orchestrator = PipelineOrchestrator.__new__(PipelineOrchestrator)
    orchestrator.console = Console(file=console_output, width=200)
    orchestrator.icons = PipelineOrchestrator.icons
    orchestrator.archive = archive
    orchestrator.config = SimpleNamespace()  # configured_source_keys falls back to {}

    fetched = [item(SourceType.RSS, feed_name="Good", source_key="rss/Good")]
    for _ in range(3):
        orchestrator.run_id = archive.start_run(NOW)
        orchestrator.last_fetch_report = FetchReport(
            [SourceFetchOutcome("RSS Feeds", "success", items=fetched, source_errors={"rss/Dead": "404"})]
        )
        orchestrator._finish_archive("success", fetched, fetched)

    report = {h.source_key: h for h in assess_health(archive.source_run_rows(NOW - timedelta(days=1)))}
    assert report["rss/Dead"].status is HealthStatus.DEAD
    assert (report["rss/Good"].items, report["rss/Good"].selected) == (3, 3)
    assert "rss/Dead: dead, failed the last 3 runs" in console_output.getvalue()


def test_sources_cli_prints_json_report(tmp_path, capsys) -> None:
    archive = ItemArchive(tmp_path / "archive.sqlite3")
    run_id = archive.start_run(datetime.now(timezone.utc))
    archive.record_source_runs(
        run_id, [SourceRunOutcome("rss/A", "rss", "failure", error="HTTPStatusError: 404")]
    )
    archive.finish_run(run_id, "success")

    assert sources_main(["--data-dir", str(tmp_path), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["sources"][0]["source"] == "rss/A"
    assert payload["sources"][0]["status"] == "failing"
    assert sources_main(["--data-dir", str(tmp_path / "missing")]) == 1
