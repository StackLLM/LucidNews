"""Quality overview of the watch (lot 19): every indicator from the archive."""

import asyncio
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from lucidnews.ai.budget import AILimit
from lucidnews.archive import ItemArchive
from lucidnews.models import (
    ArchiveConfig,
    ClassificationResult,
    ContentAnalysis,
    ContentItem,
    DigestConfig,
    ProcessingResult,
    SourceType,
)
from lucidnews.quality_overview import quality_overview
from lucidnews.reliability import ReliabilityAssessment, ReliabilityLabel, SourceTier
from lucidnews.source_health import SourceRunOutcome
from lucidnews.web_api import build_context, resolve
from tests.test_archive import make_orchestrator

ROOT = Path(__file__).resolve().parents[1]
CONFIGURED = {"rss/A": "rss", "rss/B": "rss", "rss/Quiet": "rss"}


def item(item_id: str, feed: str, hours_ago: float, label: ReliabilityLabel | None = ReliabilityLabel.RELIABLE,
         categories=("ai",), skipped: bool = False) -> ContentItem:
    processing = ProcessingResult(
        classification=ClassificationResult(profile="tech-news", method="source_override"),
        analysis=None if skipped else ContentAnalysis(score=8, reason="r", summary="s", categories=list(categories)),
        ai_skipped=AILimit.PROVIDER_QUOTA if skipped else None,
    )
    if label is not None and not skipped:
        processing.reliability = ReliabilityAssessment(label=label, source_tier=SourceTier.REPUTABLE)
    return ContentItem(
        id=item_id,
        source_type=SourceType.RSS,
        title=item_id,
        url=f"https://example.com/{item_id}",
        published_at=datetime.now(timezone.utc) - timedelta(hours=hours_ago),
        metadata={"feed_name": feed},
        processing=processing,
    )


@pytest.fixture
def archive(tmp_path) -> ItemArchive:
    archive = ItemArchive(tmp_path / "archive.sqlite3")
    now = datetime.now(timezone.utc)

    # A run recorded before the selection counters existed.
    old = archive.start_run(now - timedelta(days=1))
    archive.record_items(old, [item("a1", "A", 30)], selected=True)
    archive.record_source_runs(old, [SourceRunOutcome("rss/A", "rss", "success", 4, 1),
                                     SourceRunOutcome("rss/B", "rss", "failure", error="HTTP 503")])
    archive.finish_run(old, "success")

    new = archive.start_run(now - timedelta(days=1))
    archive.record_items(new, [item("drop", "B", 3, categories=("web",))])
    archive.record_items(new, [
        item("a2", "A", 2, label=ReliabilityLabel.RUMOR),
        item("b1", "B", 1, categories=("cybersecurity",)),
        item("q1", "A", 5, skipped=True),
    ], selected=True)
    archive.record_source_runs(new, [SourceRunOutcome("rss/A", "rss", "success", 6, 2),
                                     SourceRunOutcome("rss/B", "rss", "success", 2, 1)])
    archive.record_selection_stats(new, url_merged=2, topic_merged=1, above_threshold=4)
    archive.finish_run(new, "success")
    return archive


def overview(archive: ItemArchive, **kwargs):
    return quality_overview(
        archive, days=kwargs.pop("days", 14), configured_sources=CONFIGURED,
        digest=DigestConfig(watched_categories=["ai", "cybersecurity", "databases"]), **kwargs,
    )


def test_every_indicator_comes_from_the_archive(archive) -> None:
    result = overview(archive)

    assert result["runs"] == 2 and result["published"] == 4
    assert result["coverage"] == {"watched": 3, "gaps": ["ai", "cybersecurity", "databases"], "analyzed": 4}

    diversity = result["diversity"]
    assert diversity["active_sources"] == 2 and diversity["configured_sources"] == 3
    assert diversity["top_collected"] == {"source": "rss/A", "count": 10, "share": round(10 / 12, 4)}
    assert diversity["top_published"] == {"source": "rss/A", "count": 3, "share": 0.75}

    health = result["health"]
    assert health["never_collected"] == 1  # rss/Quiet
    assert health["recent_errors"] == [
        {"source": "rss/B", "error": "HTTP 503", "at": archive.list_runs()[1].started_at}
    ]
    assert sum(health["by_status"].values()) == 2

    freshness = result["freshness"]
    assert freshness["items"] == 4
    assert freshness["median_hours"] == pytest.approx(3.5, abs=0.2)  # 1, 2, 5 and 30 hours old
    assert freshness["within_24h"] == 0.75


def test_runs_without_counters_are_counted_apart(archive) -> None:
    selection = overview(archive)["selection"]

    assert selection["runs_with_data"] == 1 and selection["runs_without_data"] == 1
    assert (selection["url_merged"], selection["topic_merged"], selection["above_threshold"]) == (2, 1, 4)
    old, new = selection["per_run"]
    assert old["url_merged"] is None and old["above_threshold"] is None  # never invented
    assert new["fetched"] == 4 and new["selected"] == 3


def test_reliability_of_what_was_published(archive) -> None:
    reliability = overview(archive)["reliability"]

    assert reliability["labels"] == {"confirmed": 0, "reliable": 2, "unverified": 0, "rumor": 1}
    assert reliability["unanalyzed"] == 1 and reliability["unlabeled"] == 0


def test_an_empty_period_has_no_made_up_values(tmp_path) -> None:
    result = overview(ItemArchive(tmp_path / "archive.sqlite3"))

    assert result["runs"] == 0 and result["published"] == 0
    assert result["freshness"] == {"items": 0, "median_hours": None, "p90_hours": None, "within_24h": None}
    assert result["diversity"]["top_collected"] is None and result["diversity"]["top_published"] is None
    assert result["selection"]["fetched"] is None and result["selection"]["runs_without_data"] == 0
    assert result["filtering"] is None


def test_the_evaluation_summary_flags_a_small_sample(archive) -> None:
    report = {"annotated": 4, "compared": 3, "small_sample": True,
              "selection": {"precision": 1.0, "recall": 0.6667}, "reliability": {"false_reliable": 1}}

    assert overview(archive, evaluation=report)["filtering"] == {
        "annotated": 4, "compared": 3, "small_sample": True, "precision": 1.0, "recall": 0.6667, "false_reliable": 1,
        "min_sample": 30,
    }


def test_route_shows_the_evaluation_only_on_the_local_api(tmp_path, monkeypatch) -> None:
    shutil.copy(ROOT / "data" / "config.example.json", tmp_path / "config.json")
    ItemArchive(tmp_path / "archive.sqlite3")
    monkeypatch.chdir(ROOT)

    status, body = resolve(build_context(str(tmp_path), None, local_features=True), "/api/quality/overview", {"days": ["7"]})
    assert status == 200 and body["days"] == 7
    assert body["filtering"]["annotated"] == 0 and body["filtering"]["small_sample"] is True

    status, body = resolve(build_context(str(tmp_path), None), "/api/quality/overview", {})
    assert status == 200 and body["filtering"] is None
    assert resolve(build_context(str(tmp_path), None), "/api/quality/overview", {"days": ["91"]})[0] == 400


def test_an_empty_run_records_zero_counters(tmp_path, monkeypatch) -> None:
    orchestrator = make_orchestrator(None)
    orchestrator.storage = SimpleNamespace(data_dir=tmp_path)
    orchestrator.config = SimpleNamespace(archive=ArchiveConfig(), email=None, collection=SimpleNamespace(time_window_hours=24))
    orchestrator.email_manager = None
    orchestrator.webhook_notifier = None
    orchestrator.last_fetch_report = None

    async def fetch_all_sources(since):  # type: ignore[no-untyped-def]
        return []

    monkeypatch.setattr(orchestrator, "fetch_all_sources", fetch_all_sources)
    asyncio.run(orchestrator.run())

    run = ItemArchive(tmp_path / "archive.sqlite3").list_runs()[0]
    assert run.status == "empty"
    assert (run.url_merged_count, run.topic_merged_count, run.above_threshold_count) == (0, 0, 0)
