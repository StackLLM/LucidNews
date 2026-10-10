"""Watched domains, coverage from the archive, recommended sources (lot 18)."""

import json
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError
from rich.console import Console

from src.archive import ItemArchive
from src.coverage import CoverageThresholds, compute_coverage
from src.models import (
    ClassificationResult,
    Config,
    ContentAnalysis,
    ContentItem,
    DigestConfig,
    ProcessingConfig,
    ProcessingResult,
    ProfileSettingsConfig,
    SourceType,
)
from src.orchestrator import PipelineOrchestrator
from src.processing import ProfileRegistry
from src.reliability import ReliabilityAssessment, ReliabilityLabel, SourceTier
from src.settings_api import SettingsService
from src.source_catalog import load_catalog, recommendations
from src.taxonomy import Category
from src.web_api import build_context, resolve

ROOT = Path(__file__).resolve().parents[1]
NOW = datetime.now(timezone.utc)


def item(
    item_id: str,
    categories: list[str],
    feed: str = "Feed A",
    *,
    score: float | None = 8.0,
    hours_ago: float = 5,
    label: ReliabilityLabel | None = None,
) -> ContentItem:
    processing = ProcessingResult(
        classification=ClassificationResult(profile="tech-news", method="source_override"),
        analysis=ContentAnalysis(score=score, reason="r", summary="s", categories=categories) if score is not None else None,
    )
    if label is not None:
        processing.reliability = ReliabilityAssessment(label=label, source_tier=SourceTier.REPUTABLE)
    return ContentItem(
        id=item_id,
        source_type=SourceType.RSS,
        title=item_id,
        url=f"https://example.com/{item_id}",
        published_at=NOW - timedelta(hours=hours_ago),
        metadata={"feed_name": feed},
        processing=processing,
    )


# Coverage --------------------------------------------------------------------------


def by_category(result: dict) -> dict:
    return {entry["category"]: entry for entry in result["categories"]}


def test_coverage_counts_only_what_the_archive_holds() -> None:
    items = [
        item("a1", ["ai"], "Feed A", hours_ago=2, label=ReliabilityLabel.CONFIRMED),
        item("a2", ["ai", "cloud"], "Feed B", hours_ago=30, label=ReliabilityLabel.RUMOR),
        item("a3", ["ai"], "Old feed", hours_ago=50),  # source no longer configured
        item("s1", ["cybersecurity"], "Feed A"),
        item("u1", [], score=None),  # not analyzed: no category to count
        item("x1", []),  # analyzed, no category
    ]
    configured = {"rss/Feed A": "rss", "rss/Feed B": "rss"}

    result = compute_coverage(
        items, {"a1"}, configured, ["ai", "cybersecurity"], CoverageThresholds(min_sources=2, min_items=3)
    )

    assert result["analyzed"] == 5 and result["unanalyzed"] == 1 and result["uncategorized"] == 1
    ai = by_category(result)["ai"]
    assert ai["items"] == 3 and ai["published"] == 1
    assert ai["active_sources"] == 2  # Old feed fed it but is not configured any more
    assert {source["source"]: source["configured"] for source in ai["sources"]} == {
        "rss/Feed A": True, "rss/Feed B": True, "rss/Old feed": False,
    }
    assert ai["trusted_share"] == round(1 / 3, 4)
    assert ai["latest_at"] == items[0].published_at.isoformat()
    assert ai["gap"] is False

    security = by_category(result)["cybersecurity"]
    assert security["gap"] is True and security["gap_reasons"] == ["sources", "items"]
    cloud = by_category(result)["cloud"]
    assert cloud["watched"] is False and cloud["gap"] is False  # gaps only for watched domains
    empty = by_category(result)["databases"]
    assert empty["items"] == 0 and empty["latest_at"] is None and empty["trusted_share"] is None
    assert [entry["category"] for entry in result["categories"]] == [category.value for category in Category]


def test_coverage_route_reads_the_archive_and_the_watched_domains(tmp_path, monkeypatch) -> None:
    config = json.loads((ROOT / "data" / "config.example.json").read_text())
    config["digest"]["watched_categories"] = ["ai", "databases"]
    (tmp_path / "config.json").write_text(json.dumps(config))
    archive = ItemArchive(tmp_path / "archive.sqlite3")
    run_id = archive.start_run(NOW - timedelta(days=1))
    archive.record_items(run_id, [item("a1", ["ai"], "OpenAI News"), item("a2", ["ai"], "Google DeepMind")], selected=True)
    archive.record_items(run_id, [item("old", ["databases"], "PostgreSQL News", hours_ago=24 * 20)])
    monkeypatch.chdir(ROOT)
    ctx = build_context(str(tmp_path), None)

    status, body = resolve(ctx, "/api/coverage", {"days": ["14"]})

    assert status == 200
    assert body["watched"] == ["ai", "databases"] and body["min_sources"] == 2 and body["min_items"] == 3
    categories = by_category(body)
    assert categories["ai"]["items"] == 2 and categories["ai"]["published"] == 2
    assert categories["ai"]["active_sources"] == 2 and categories["ai"]["gap_reasons"] == ["items"]
    assert categories["databases"]["items"] == 0 and categories["databases"]["gap"] is True  # older than 14 days
    assert resolve(ctx, "/api/coverage", {"days": ["0"]})[0] == 400


# Catalog ---------------------------------------------------------------------------


def test_catalog_comes_from_the_shipped_files_only() -> None:
    catalog = load_catalog()
    known = {category.value for category in Category}

    assert len(catalog) >= 40
    assert all(entry.category in known for entry in catalog)
    assert len({entry.key.lower() for entry in catalog}) == len(catalog)
    assert not any("${" in json.dumps(entry.values) or "wechat2rss" in json.dumps(entry.values) for entry in catalog)
    assert {"rss/OpenAI News", "github/postgres/postgres", "reddit/r/netsec", "github/@torvalds"} <= {
        entry.key for entry in catalog
    }
    assert {category.value for category in Category} <= {entry.category for entry in catalog}  # every domain has some


def test_recommendations_leave_out_every_configured_source() -> None:
    config = Config.model_validate(json.loads((ROOT / "data" / "config.example.json").read_text()))
    config.sources.rss[0].enabled = False  # disabled is still configured
    config.sources.rss.append(config.sources.rss[1].model_copy(update={"name": "Renamed DeepMind"}))
    del config.sources.rss[1]  # same feed URL under another name
    config.sources.reddit.subreddits = [config.sources.reddit.subreddits[0].model_copy(update={"subreddit": "NETSEC"})]

    keys = {entry.key for entry in recommendations(load_catalog(), config)}

    assert "rss/OpenAI News" not in keys
    assert "rss/Google DeepMind" not in keys
    assert "reddit/r/netsec" not in keys
    assert "reddit/r/LocalLLaMA" in keys  # removed from this config: recommended again
    ai_only = recommendations(load_catalog(), config, "ai")
    assert ai_only and all(entry.category == "ai" for entry in ai_only)


def test_catalog_route(tmp_path, monkeypatch) -> None:
    shutil.copy(ROOT / "data" / "config.example.json", tmp_path / "config.json")
    ItemArchive(tmp_path / "archive.sqlite3")
    monkeypatch.chdir(ROOT)
    ctx = build_context(str(tmp_path), None)

    status, body = resolve(ctx, "/api/catalog", {"category": ["cybersecurity"]})

    assert status == 200
    keys = {entry["key"] for entry in body["entries"]}
    assert "rss/Schneier on Security" in keys and "rss/Krebs on Security" not in keys  # Krebs is configured
    assert all(entry["kind"] and entry["values"] for entry in body["entries"])
    assert resolve(ctx, "/api/catalog", {"category": ["finance"]})[0] == 400


# Watched domains -------------------------------------------------------------------


def test_watched_categories_are_validated_and_normalized() -> None:
    assert DigestConfig().watched_categories == [category.value for category in Category]
    assert DigestConfig(watched_categories=["web", "ai", "ai"]).watched_categories == ["ai", "web"]
    with pytest.raises(ValidationError):
        DigestConfig(watched_categories=["finance"])
    with pytest.raises(ValidationError):
        DigestConfig(watched_categories=[], only_watched_categories=True)


def orchestrator(digest: DigestConfig) -> PipelineOrchestrator:
    orchestrator = PipelineOrchestrator.__new__(PipelineOrchestrator)
    orchestrator.config = SimpleNamespace(
        digest=digest,
        processing=ProcessingConfig(profile_settings={"tech-news": ProfileSettingsConfig(threshold=7.0)}),
    )
    orchestrator.console = Console(record=True)
    return orchestrator


def test_only_watched_domains_reach_the_digest() -> None:
    ai, web, none = item("ai", ["ai"]), item("web", ["web", "cloud"]), item("none", [])

    follow_all = orchestrator(DigestConfig(watched_categories=["ai"]))
    assert all(follow_all.passes_profile_filter(entry) for entry in (ai, web, none))  # option off

    only = orchestrator(DigestConfig(watched_categories=["ai", "cloud"], only_watched_categories=True))
    assert only.passes_profile_filter(ai)
    assert only.passes_profile_filter(web)  # one of its categories is watched
    assert not only.passes_profile_filter(none)
    assert not only.passes_profile_filter(item("low", ["ai"], score=5))  # the score threshold still applies


def test_watched_domains_are_saved_from_the_settings_api(tmp_path) -> None:
    shutil.copy(ROOT / "data" / "config.example.json", tmp_path / "config.json")
    service = SettingsService(
        config_path=tmp_path / "config.json",
        backup_dir=tmp_path / "backups",
        profiles=ProfileRegistry.load(ROOT / "profiles", "tech-news"),
        env_path=tmp_path / ".env",
    )
    _, current = service.get()
    assert current["values"]["digest"]["only_watched_categories"] is False

    status, body = service.update(
        {
            "version": current["version"],
            "values": {"digest": {"watched_categories": ["web", "ai"], "only_watched_categories": True,
                                  "coverage_min_sources": 1}},
        }
    )
    assert status == 200, body
    stored = json.loads((tmp_path / "config.json").read_text())["digest"]
    assert stored["watched_categories"] == ["ai", "web"] and stored["only_watched_categories"] is True
    assert stored["coverage_min_sources"] == 1

    _, current = service.get()
    status, body = service.update(
        {"version": current["version"], "values": {"digest": {"watched_categories": []}}}
    )
    assert status == 422  # publishing only watched domains needs at least one
