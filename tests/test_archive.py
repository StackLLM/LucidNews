import asyncio
from datetime import datetime, timedelta, timezone
from io import StringIO
from types import SimpleNamespace

from rich.console import Console

from src.archive import ItemArchive, content_hash
from src.models import (
    ArchiveConfig,
    ClassificationResult,
    ContentAnalysis,
    ContentItem,
    ProcessingResult,
    SourceType,
)
from src.orchestrator import FetchReport, PipelineOrchestrator, SourceFetchOutcome
from src.reliability.assess import ReliabilityPolicy

NOW = datetime(2026, 10, 6, 12, 0, tzinfo=timezone.utc)


def make_item(item_id: str, *, score: float | None = None, content: str = "body", hours_ago: int = 1):
    item = ContentItem(
        id=item_id,
        source_type=SourceType.RSS,
        title=f"{item_id} title",
        url=f"https://lwn.net/{item_id}",
        content=content,
        published_at=NOW - timedelta(hours=hours_ago),
    )
    if score is not None:
        item.processing = ProcessingResult(
            classification=ClassificationResult(profile="tech-news", method="ai_match"),
            analysis=ContentAnalysis(score=score, reason="r", summary="s", categories=["web"]),
        )
    return item


def test_runs_and_items_are_recorded_and_upserted(tmp_path) -> None:
    archive = ItemArchive(tmp_path / "archive.sqlite3")
    run_id = archive.start_run(NOW - timedelta(hours=24))

    archive.record_items(run_id, [make_item("a"), make_item("b")])
    archive.record_items(run_id, [make_item("a", score=8.0)], selected=True)
    archive.record_items(run_id, [make_item("a", score=8.0)])  # later write keeps "selected"
    archive.finish_run(run_id, "success", fetch_report={"status": "success"})

    run = archive.get_run(run_id)
    assert (run.status, run.fetched_count, run.selected_count) == ("success", 2, 1)
    assert archive.get_item("a").processing.analysis.score == 8.0
    assert archive.get_item("missing") is None
    assert [r.id for r in archive.list_runs()] == [run_id]


def test_items_between_filters_by_date_and_selection(tmp_path) -> None:
    archive = ItemArchive(tmp_path / "archive.sqlite3")
    run_id = archive.start_run(NOW)
    archive.record_items(run_id, [make_item("old", score=9.0, hours_ago=200), make_item("low", score=5.0)])
    archive.record_items(run_id, [make_item("top", score=9.5)], selected=True)

    week = archive.items_between(NOW - timedelta(days=7))
    assert [item.id for item in week] == ["top", "low"]
    assert [item.id for item in archive.items_between(NOW - timedelta(days=7), selected_only=True)] == ["top"]


def test_archive_survives_reopening(tmp_path) -> None:
    path = tmp_path / "nested" / "archive.sqlite3"
    run_id = ItemArchive(path).start_run(NOW)
    ItemArchive(path).record_items(run_id, [make_item("a")])

    assert ItemArchive(path).get_item("a").title == "a title"


def make_orchestrator(archive: ItemArchive | None, reuse: bool = True) -> PipelineOrchestrator:
    orchestrator = PipelineOrchestrator.__new__(PipelineOrchestrator)
    orchestrator.console = Console(file=StringIO())
    orchestrator.icons = PipelineOrchestrator.icons
    orchestrator.archive = archive
    orchestrator.run_id = None
    orchestrator.reliability_policy = ReliabilityPolicy()
    orchestrator.config = SimpleNamespace(archive=ArchiveConfig(reuse_analysis=reuse))
    return orchestrator


def test_unchanged_items_reuse_stored_analysis(tmp_path) -> None:
    archive = ItemArchive(tmp_path / "archive.sqlite3")
    run_id = archive.start_run(NOW)
    archive.record_items(
        run_id,
        [make_item("same", score=8.0), make_item("edited", score=8.0), make_item("failed")],
    )
    orchestrator = make_orchestrator(archive)
    fresh = [make_item("same"), make_item("edited", content="new body"), make_item("failed"), make_item("new")]

    remaining = orchestrator._reuse_archived_analyses(fresh)

    assert [item.id for item in remaining] == ["edited", "failed", "new"]
    reused = fresh[0]
    assert reused.processing.analysis.score == 8.0
    assert reused.processing.reliability.source_tier.value == "reputable"
    assert content_hash(reused) == content_hash(make_item("same"))


def test_reuse_can_be_disabled_and_needs_an_archive(tmp_path) -> None:
    archive = ItemArchive(tmp_path / "archive.sqlite3")
    run_id = archive.start_run(NOW)
    archive.record_items(run_id, [make_item("same", score=8.0)])
    items = [make_item("same")]

    assert make_orchestrator(archive, reuse=False)._reuse_archived_analyses(items) == items
    assert make_orchestrator(None)._reuse_archived_analyses(items) == items


def test_failed_run_is_recorded(tmp_path, monkeypatch) -> None:
    orchestrator = make_orchestrator(None)
    orchestrator.storage = SimpleNamespace(data_dir=tmp_path)
    orchestrator.config = SimpleNamespace(
        archive=ArchiveConfig(),
        email=None,
        collection=SimpleNamespace(time_window_hours=24),
    )
    orchestrator.email_manager = None
    orchestrator.webhook_notifier = None
    orchestrator.last_fetch_report = None

    async def fetch_all_sources(since):  # type: ignore[no-untyped-def]
        orchestrator.last_fetch_report = FetchReport([SourceFetchOutcome("RSS Feeds", "failure", error="down")])
        return []

    monkeypatch.setattr(orchestrator, "fetch_all_sources", fetch_all_sources)

    try:
        asyncio.run(orchestrator.run())
    except RuntimeError:
        pass

    run = ItemArchive(tmp_path / "archive.sqlite3").list_runs()[0]
    assert run.status == "failed"
    assert "All 1 attempted sources failed" in run.error


def test_broken_archive_never_breaks_the_pipeline(tmp_path) -> None:
    blocker = tmp_path / "not-a-dir"
    blocker.write_text("x")
    orchestrator = make_orchestrator(None)
    orchestrator.storage = SimpleNamespace(data_dir=blocker)
    orchestrator.config = SimpleNamespace(archive=ArchiveConfig())

    assert orchestrator._open_archive() is None
    orchestrator._archive("record_items", [make_item("a")])  # no archive, no error


def test_unanalyzed_copy_never_overwrites_a_stored_analysis(tmp_path) -> None:
    archive = ItemArchive(tmp_path / "archive.sqlite3")
    first = archive.start_run(NOW)
    archive.record_items(first, [make_item("a", score=8.0)])
    second = archive.start_run(NOW)

    archive.record_items(second, [make_item("a")])  # same content, not analyzed yet
    assert archive.get_item("a").processing.analysis.score == 8.0

    archive.record_items(second, [make_item("a", content="changed")])  # new content wins
    assert archive.get_item("a").processing is None
    assert archive.get_run(second) is not None
