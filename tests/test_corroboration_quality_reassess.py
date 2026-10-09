"""Wider corroboration, source quality tie-breaker and archive re-assessment."""

import asyncio
import json
import shutil
from datetime import datetime, timedelta, timezone
from io import StringIO
from pathlib import Path
from types import SimpleNamespace

from rich.console import Console

import src.orchestrator as orchestrator_module
from src.archive import ItemArchive
from src.models import ClassificationResult, ContentAnalysis, ContentItem, ProcessingResult, SourceType
from src.orchestrator import PipelineOrchestrator
from src.reassess_cli import main as reassess_main
from src.reassess_cli import reassess
from src.reliability import ClaimAssessment, ClaimStatus, ReliabilityLabel
from src.reliability.assess import ReliabilityPolicy, assess_item
from src.source_quality import compute_source_quality

ROOT = Path(__file__).resolve().parents[1]
NOW = datetime.now(timezone.utc)


def make_item(
    item_id: str,
    url: str,
    score: float = 8.0,
    *,
    feed: str = "Feed",
    claim: ClaimStatus = ClaimStatus.REPORTED,
    hours_ago: int = 1,
    profile: str = "tech-news",
) -> ContentItem:
    item = ContentItem(
        id=item_id,
        source_type=SourceType.RSS,
        title=f"Title {item_id}",
        url=url,
        published_at=NOW - timedelta(hours=hours_ago),
        metadata={"feed_name": feed},
        processing=ProcessingResult(
            classification=ClassificationResult(profile=profile, method="source_override"),
            analysis=ContentAnalysis(
                score=score, reason="r", summary=f"Summary {item_id}", claim=ClaimAssessment(status=claim)
            ),
        ),
    )
    item.processing.reliability = assess_item(item)
    return item


def make_orchestrator(**reliability) -> PipelineOrchestrator:  # type: ignore[no-untyped-def]
    orchestrator = PipelineOrchestrator.__new__(PipelineOrchestrator)
    orchestrator.console = Console(file=StringIO())
    orchestrator.icons = PipelineOrchestrator.icons
    orchestrator.archive = None
    orchestrator.reliability_policy = ReliabilityPolicy()
    orchestrator.profiles = SimpleNamespace(default_profile="tech-news")
    orchestrator.config = SimpleNamespace(
        ai=SimpleNamespace(),
        processing=SimpleNamespace(profile_settings={}),
        digest=SimpleNamespace(source_quality_days=30),
        reliability=SimpleNamespace(
            exclude_labels=[],
            corroboration_lookback_hours=reliability.get("lookback", 72),
            corroboration_max_references=reliability.get("limit", 30),
        ),
    )
    return orchestrator


class FakeDedupClient:
    def __init__(self, groups):  # type: ignore[no-untyped-def]
        self.groups = groups
        self.prompts: list[str] = []

    async def complete(self, system, user, temperature=None, max_tokens=None):  # type: ignore[no-untyped-def]
        self.prompts.append(user)
        return json.dumps({"duplicates": self.groups})


def use_client(monkeypatch, client) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(orchestrator_module, "create_ai_client", lambda config: client)


# Source quality ------------------------------------------------------------------


def test_source_quality_is_smoothed_toward_neutral() -> None:
    items = [make_item("a", "https://lwn.net/a", 10.0, feed="LWN")]
    unscored = make_item("b", "https://lwn.net/b", feed="LWN")
    unscored.processing.analysis.score = None

    quality = compute_source_quality([*items, unscored])

    lwn = quality["rss/LWN"]
    assert lwn.items == 1 and lwn.trusted_share == 1.0
    assert lwn.score == round((1 * 1.0 + 5 * 0.5) / 6, 4)  # one item cannot reach 1.0


def test_source_quality_uses_the_current_registry_when_given() -> None:
    item = make_item("a", "https://unknown-blog.example/a", 6.0, feed="Blog")
    stale = compute_source_quality([item])["rss/Blog"]

    policy = ReliabilityPolicy.with_overrides({"unknown-blog.example": "reputable"})
    fresh = compute_source_quality([item], policy)["rss/Blog"]

    assert stale.trusted_share == 0.0 and fresh.trusted_share == 1.0


def test_quality_only_breaks_ties_between_equal_scores() -> None:
    orchestrator = make_orchestrator()
    orchestrator.source_quality = {"rss/Good": 0.9, "rss/Weak": 0.2}
    weak_high = make_item("weak-high", "https://a.example/1", 8.5, feed="Weak")
    weak_tie = make_item("weak-tie", "https://a.example/2", 8.0, feed="Weak")
    good_tie = make_item("good-tie", "https://b.example/3", 8.0, feed="Good")

    ranked = sorted([weak_tie, good_tie, weak_high], key=orchestrator._rank_key, reverse=True)

    assert [item.id for item in ranked] == ["weak-high", "good-tie", "weak-tie"]


def test_archive_signals_load_quality_and_earlier_reports(tmp_path) -> None:
    archive = ItemArchive(tmp_path / "archive.sqlite3")
    run_id = archive.start_run(NOW - timedelta(days=2))
    archive.record_items(
        run_id,
        [
            make_item("old", "https://lwn.net/old", feed="LWN", hours_ago=30),
            make_item("ancient", "https://lwn.net/ancient", feed="LWN", hours_ago=24 * 10),
            make_item("current", "https://lwn.net/current", feed="LWN"),
        ],
    )
    orchestrator = make_orchestrator()
    orchestrator.archive = archive

    orchestrator._load_archive_signals([make_item("current", "https://lwn.net/current")])

    assert set(orchestrator.source_quality) == {"rss/LWN"}
    assert [item.id for item in orchestrator.archived_references] == ["old"]  # 72 h, not this run


# Wider corroboration -------------------------------------------------------------


def test_references_are_official_or_reputable_scored_and_per_profile() -> None:
    orchestrator = make_orchestrator(limit=2)
    candidate = make_item("candidate", "https://blog.example/x")
    below = make_item("below", "https://lwn.net/x", 3.0, hours_ago=2)
    unknown = make_item("unknown", "https://random.example/x", 3.0)
    unscored = make_item("unscored", "https://openai.com/x")
    unscored.processing.analysis.score = None
    other_profile = make_item("other", "https://openai.com/y", profile="tech-blog")
    orchestrator.archived_references = [
        make_item("archived", "https://openai.com/z", hours_ago=20),
        make_item("archived-older", "https://lwn.net/z", hours_ago=40),
    ]

    refs = orchestrator._corroboration_references(
        [candidate], [candidate, below, unknown, unscored, other_profile]
    )

    assert [item.id for item in refs["tech-news"]] == ["below", "archived"]  # newest first, capped at 2
    assert [item.id for item in refs["tech-blog"]] == ["other"]
    assert make_orchestrator(limit=0)._corroboration_references([candidate], [below]) == {}


def test_a_reference_corroborates_without_being_kept_or_dropped(monkeypatch) -> None:
    client = FakeDedupClient([[2, 0], [1, 3]])  # 2 and 3 are references
    use_client(monkeypatch, client)
    items = [make_item("a", "https://blog.example/a"), make_item("b", "https://blog.example/b")]
    refs = [make_item("r1", "https://openai.com/r1"), make_item("r2", "https://lwn.net/r2")]

    result = asyncio.run(make_orchestrator().merge_topic_duplicates(items, references=refs))

    assert [item.id for item in result] == ["a", "b"]
    assert items[0].metadata["corroborating_urls"] == ["https://openai.com/r1"]
    assert items[1].metadata["corroborating_urls"] == ["https://lwn.net/r2"]
    assert "[2] (reference) Title r1" in client.prompts[0]
    assert "never first in a group" in client.prompts[0]


def test_a_single_item_is_checked_against_references(monkeypatch) -> None:
    client = FakeDedupClient([[0, 1]])
    use_client(monkeypatch, client)
    item = make_item("a", "https://blog.example/a")

    asyncio.run(
        make_orchestrator().merge_topic_duplicates([item], references=[make_item("r", "https://lwn.net/r")])
    )

    assert item.metadata["corroborating_urls"] == ["https://lwn.net/r"]
    assert asyncio.run(make_orchestrator().merge_topic_duplicates([item])) == [item]
    assert len(client.prompts) == 1  # no references, no call for a single item


def test_groups_of_references_only_are_ignored(monkeypatch) -> None:
    use_client(monkeypatch, FakeDedupClient([[2, 3], [0, 99, "x"]]))
    items = [make_item("a", "https://blog.example/a"), make_item("b", "https://blog.example/b")]
    refs = [make_item("r1", "https://openai.com/r1"), make_item("r2", "https://lwn.net/r2")]

    result = asyncio.run(make_orchestrator().merge_topic_duplicates(items, references=refs))

    assert [item.id for item in result] == ["a", "b"]
    assert "corroborating_urls" not in items[0].metadata


def test_a_below_threshold_official_report_lifts_the_digest_item(monkeypatch) -> None:
    use_client(monkeypatch, FakeDedupClient([[0, 1]]))
    orchestrator = make_orchestrator()
    orchestrator.config.processing.profile_settings = {"tech-news": SimpleNamespace(threshold=7.0, topic_dedup=True)}
    blog = make_item("blog", "https://blog.example/news", 8.0, claim=ClaimStatus.UNVERIFIED)
    official = make_item("official", "https://openai.com/index/news", 5.0, claim=ClaimStatus.CONFIRMED)
    assert blog.processing.reliability.label is ReliabilityLabel.UNVERIFIED

    result = asyncio.run(orchestrator.filter_items([blog, official], apply_balance=False))

    assert [item.id for item in result.items] == ["blog"]
    assert blog.processing.reliability.label is ReliabilityLabel.CONFIRMED
    assert blog.processing.reliability.corroborated_by == ["openai.com"]


# Archive re-assessment -------------------------------------------------------------


def test_reassess_updates_labels_without_touching_the_analysis(tmp_path) -> None:
    archive = ItemArchive(tmp_path / "archive.sqlite3")
    run_id = archive.start_run(NOW - timedelta(days=1))
    item = make_item("blog", "https://unknown-blog.example/a", 7.0, claim=ClaimStatus.REPORTED)
    assert item.processing.reliability.label is ReliabilityLabel.UNVERIFIED
    archive.record_items(run_id, [item, make_item("lwn", "https://lwn.net/a")], selected=True)
    policy = ReliabilityPolicy.with_overrides({"unknown-blog.example": "reputable"})

    changes, before, after = reassess(archive, policy)
    assert [(changed.id, old) for changed, old in changes] == [("blog", "unverified")]
    assert before["unverified"] == 1 and after["reliable"] == 2
    assert archive.get_item("blog").processing.reliability.label is ReliabilityLabel.UNVERIFIED  # preview

    assert archive.update_reliability(changed for changed, _ in changes) == 1
    stored = archive.get_item("blog")
    assert stored.processing.reliability.label is ReliabilityLabel.RELIABLE
    assert stored.processing.analysis.score == 7.0
    assert reassess(archive, policy)[0] == []


def test_reassess_cli_previews_then_applies(tmp_path, capsys) -> None:
    config = json.loads((ROOT / "data" / "config.example.json").read_text())
    config["reliability"] = {"domains": {"unknown-blog.example": "reputable"}}
    (tmp_path / "config.json").write_text(json.dumps(config))
    shutil.copytree(ROOT / "profiles", tmp_path / "profiles")
    archive = ItemArchive(tmp_path / "archive.sqlite3")
    archive.record_items(
        archive.start_run(NOW), [make_item("blog", "https://unknown-blog.example/a")], selected=True
    )

    assert reassess_main(["-d", str(tmp_path), "--json"]) == 0
    preview = json.loads(capsys.readouterr().out)
    assert preview["applied"] is False
    assert preview["changed"] == [
        {"id": "blog", "title": "Title blog", "from": "unverified", "to": "reliable"}
    ]
    assert archive.get_item("blog").processing.reliability.label is ReliabilityLabel.UNVERIFIED

    assert reassess_main(["-d", str(tmp_path), "--apply", "--json"]) == 0
    capsys.readouterr()
    assert archive.get_item("blog").processing.reliability.label is ReliabilityLabel.RELIABLE
