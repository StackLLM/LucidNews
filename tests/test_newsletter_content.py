"""Lot 21: detail levels, weekly digest and the preview shared with the sending path."""

import asyncio
import json
from datetime import datetime, timedelta, timezone
from io import StringIO
from pathlib import Path
from types import SimpleNamespace

import pytest
from rich.console import Console

from lucidnews.ai.summarizer import DailySummarizer
from lucidnews.archive import ItemArchive
from lucidnews.models import (
    ArtifactSource,
    ClassificationResult,
    Config,
    ContentAnalysis,
    ContentArtifact,
    ContentBlock,
    ContentItem,
    EmailConfig,
    ProcessingResult,
    SourceType,
)
from lucidnews.newsletter import DetailLevel, DigestPreferences, Frequency, Subscriber, plan_deliveries
from lucidnews.newsletter.mailer import SendSummary
from lucidnews.newsletter.preview import PreviewService
from lucidnews.newsletter.weekly import WeeklyState, iso_week, window
from lucidnews.orchestrator import PipelineOrchestrator
from lucidnews.reliability import ReliabilityAssessment
from lucidnews.storage.manager import StorageManager
from lucidnews.web_api import ApiContext, resolve
from lucidnews.subscribers_api import SubscriberService, subscriber_id

NOW = datetime.now(timezone.utc)
ROOT = Path(__file__).resolve().parent.parent


def make_config(email=None) -> Config:
    data = json.loads((ROOT / "data" / "config.example.json").read_text())
    data["ai"]["languages"] = ["en"]
    data["email"] = email
    return Config.model_validate(data)


def make_item(item_id, score, published=None, title=None, **kwargs):
    artifact = ContentArtifact(
        language="en",
        title=title or f"{item_id} title",
        blocks=[
            ContentBlock(id="lead", title="Lead", content=f"{item_id} lead text", primary=True),
            ContentBlock(id="ctx", title="Background", content=f"{item_id} background context"),
        ],
        sources=[ArtifactSource(id="s1", title="Ref one", url="https://example.com/ref")],
    )
    return ContentItem(
        id=item_id,
        source_type=SourceType.RSS,
        title=title or f"{item_id} title",
        url=f"https://example.com/{item_id}",
        published_at=published or NOW - timedelta(hours=2),
        processing=ProcessingResult(
            classification=ClassificationResult(profile="tech-news", method="ai_match"),
            analysis=ContentAnalysis(
                score=score, reason="r", summary=f"{item_id} summary", categories=["ai"], tags=["tagone"]
            ),
            reliability=ReliabilityAssessment(label="confirmed", source_tier="official"),
            artifacts={"en": artifact},
            **kwargs,
        ),
    )


def render(items, detail):
    return asyncio.run(
        DailySummarizer().generate_summary(items, "2026-10-05", 10, language="en", detail=detail)
    )


def test_brief_keeps_the_summary_and_drops_the_context() -> None:
    item = make_item("alpha", 9.0)

    brief, complete = render([item], "brief"), render([item], "complete")

    assert "alpha lead text" in brief and "alpha lead text" in complete
    assert "alpha background context" not in brief
    assert "alpha background context" in complete
    assert "Ref one" not in brief and "Ref one" in complete
    assert "tagone" not in brief and "tagone" in complete
    # What makes an item trustworthy stays in the short version.
    assert "Reliability" in brief
    assert brief != complete and len(brief) < len(complete)


def test_brief_falls_back_to_the_analysis_when_the_enrichment_has_no_lead() -> None:
    item = make_item("beta", 8.0)
    item.processing.artifacts["en"].blocks[0].primary = False

    assert "beta summary" in render([item], "brief")


def test_detail_level_defaults_to_complete_and_rejects_unknown() -> None:
    assert DigestPreferences().detail_level is DetailLevel.COMPLETE
    assert DigestPreferences(detail_level="brief").detail_level is DetailLevel.BRIEF
    with pytest.raises(ValueError):
        DigestPreferences(detail_level="verbose")
    # A subscribers.json written before the field existed still loads.
    assert Subscriber.model_validate({"email": "a@example.com", "preferences": {"language": "fr"}}).preferences.detail_level is DetailLevel.COMPLETE


def test_two_detail_levels_are_planned_as_two_deliveries() -> None:
    items = [make_item("alpha", 9.0)]
    subscribers = [
        Subscriber(email="a@example.com", preferences=DigestPreferences(detail_level="brief")),
        Subscriber(email="b@example.com", preferences=DigestPreferences(detail_level="complete")),
    ]

    plan = plan_deliveries(subscribers, items, ["en"])

    assert sorted(d.preferences.detail_level.value for d in plan.deliveries) == ["brief", "complete"]


def test_weekly_window_and_once_per_week(tmp_path) -> None:
    today = datetime(2026, 10, 12, tzinfo=timezone.utc).date()  # a Monday
    since, until, start = window(today)
    assert (until - since).days == 7 and start == "2026-10-06"

    state = WeeklyState(tmp_path / "weekly_sent.json")
    assert state.is_due(today, 0) and not state.is_due(today, 1)
    state.mark_sent(today)
    assert not state.is_due(today, 0)
    assert state.last_week() == iso_week(today) == "2026-W42"
    assert state.is_due(today + timedelta(days=7), 0)
    (tmp_path / "weekly_sent.json").write_text("not json", encoding="utf-8")
    assert state.is_due(today, 0)  # an unreadable record never blocks the digest


EMAIL = EmailConfig(imap_server="i", smtp_server="s", email_address="n@example.com", enabled=True)


def weekly_orchestrator(tmp_path, weekly_day, sent):
    storage = StorageManager(data_dir=str(tmp_path))
    storage.subscribers.add("week@example.com", DigestPreferences(frequency="weekly", detail_level="brief"))
    storage.subscribers.add("day@example.com")
    archive = ItemArchive(tmp_path / "archive.sqlite3")
    run_id = archive.start_run(NOW - timedelta(days=1))
    archive.record_items(
        run_id,
        [
            make_item("old", 9.9, published=NOW - timedelta(days=10)),
            make_item("mid", 6.0, published=NOW - timedelta(days=3)),
            make_item("top", 9.0, published=NOW - timedelta(days=1)),
            make_item("skipped", 5.0, ai_skipped="token_budget"),
        ],
        selected=True,
    )

    orchestrator = PipelineOrchestrator.__new__(PipelineOrchestrator)
    orchestrator.console = Console(file=StringIO())
    orchestrator.storage = storage
    orchestrator.icons = PipelineOrchestrator.icons
    orchestrator.profiles = SimpleNamespace(names={})
    orchestrator.archive = archive
    orchestrator.config = SimpleNamespace(
        ai=SimpleNamespace(languages=["en"]),
        digest=SimpleNamespace(profile_order=[]),
        email=EMAIL.model_copy(update={"weekly_day": weekly_day, "weekly_max_items": 2}),
    )
    orchestrator.mailer = SimpleNamespace(
        links_enabled=False,
        send_digest=lambda newsletter, recipients, kind, reference: (
            sent.append((newsletter.email, newsletter.subject, recipients)) or SendSummary(sent=len(recipients))
        ),
    )
    return orchestrator


def test_weekly_digest_is_the_best_of_the_week_and_sent_once(tmp_path) -> None:
    sent = []
    orchestrator = weekly_orchestrator(tmp_path, NOW.weekday(), sent)

    plan = asyncio.run(orchestrator.send_weekly_newsletters())

    assert [recipients for _, _, recipients in sent] == [["week@example.com"]]
    rendered, subject, _ = sent[0]
    assert subject.startswith("LucidNews — week of ")
    assert "top lead text" in rendered.text and "mid lead text" in rendered.text
    assert "old" not in rendered.text  # published more than 7 days ago
    assert "skipped" not in rendered.text  # not analyzed: never in a weekly digest
    assert "mid background context" not in rendered.text  # "brief"
    assert len(plan.deliveries[0].items) == 2

    # A second run the same day, or later that week, sends nothing more.
    assert asyncio.run(orchestrator.send_weekly_newsletters()) is None
    assert len(sent) == 1


def test_weekly_digest_waits_for_its_day(tmp_path) -> None:
    sent = []
    orchestrator = weekly_orchestrator(tmp_path, (NOW.weekday() + 1) % 7, sent)

    assert asyncio.run(orchestrator.send_weekly_newsletters()) is None
    assert sent == []


def test_preview_is_the_email_that_is_sent(tmp_path) -> None:
    sent = []
    orchestrator = weekly_orchestrator(tmp_path, NOW.weekday(), sent)
    config = make_config(EMAIL.model_dump() | {"weekly_max_items": 2})
    asyncio.run(orchestrator.send_weekly_newsletters())
    rendered, subject, _ = sent[0]

    subscriber = next(s for s in orchestrator.storage.subscribers.load() if s.email == "week@example.com")
    preview = PreviewService(orchestrator.archive, config, {}).preview(subscriber)

    assert preview["html"] == rendered.html
    assert preview["text"] == rendered.text
    assert preview["subject"] == subject
    assert (preview["frequency"], preview["detail_level"], preview["item_count"]) == ("weekly", "brief", 2)


def test_preview_daily_uses_the_latest_edition_and_the_detail_level(tmp_path) -> None:
    archive = ItemArchive(tmp_path / "archive.sqlite3")
    run_id = archive.start_run(NOW - timedelta(days=1))
    archive.record_items(run_id, [make_item("alpha", 9.0), make_item("beta", 7.0)], selected=True)
    archive.finish_run(run_id, "success")
    config = make_config()
    service = PreviewService(archive, config, {})

    brief = service.preview(Subscriber(email="a@example.com", preferences=DigestPreferences(detail_level="brief")))
    complete = service.preview(Subscriber(email="a@example.com"))

    assert brief["item_count"] == complete["item_count"] == 2
    assert brief["edition"] == run_id
    assert "alpha background context" in complete["html"]
    assert "alpha background context" not in brief["html"]
    assert brief["html"] != complete["html"]


def test_preview_escapes_what_a_source_published(tmp_path) -> None:
    archive = ItemArchive(tmp_path / "archive.sqlite3")
    run_id = archive.start_run(NOW - timedelta(days=1))
    evil = make_item("evil", 9.0, title='<script>alert(1)</script><img src=x onerror=alert(2)>')
    evil.processing.analysis.summary = '<iframe src="https://evil.example"></iframe> [x](javascript:alert(3))'
    evil.processing.artifacts["en"].blocks[0].content = '<script>steal()</script>'
    archive.record_items(run_id, [evil], selected=True)
    archive.finish_run(run_id, "success")
    config = make_config()

    html = PreviewService(archive, config, {}).preview(Subscriber(email="a@example.com"))["html"]

    for dangerous in ("<script", "<iframe", "<img", 'href="javascript:'):
        assert dangerous not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html  # shown as text, once escaped
    assert "&amp;lt;" not in html


def test_preview_route_is_local_only_and_validates_the_id(tmp_path) -> None:
    archive = ItemArchive(tmp_path / "archive.sqlite3")
    run_id = archive.start_run(NOW)
    archive.record_items(run_id, [make_item("alpha", 9.0)], selected=True)
    archive.finish_run(run_id, "success")
    storage = StorageManager(data_dir=str(tmp_path))
    storage.subscribers.add("a@example.com")
    config = make_config()
    sub_id = subscriber_id("a@example.com")

    closed = ApiContext(archive=archive)
    assert resolve(closed, f"/api/subscribers/{sub_id}/preview", {})[0] == 403

    ctx = ApiContext(
        archive=archive,
        subscribers=SubscriberService(storage.subscribers, ["en"], {}, weekly_day=3),
        previews=PreviewService(archive, config, {}),
    )
    status, body = resolve(ctx, f"/api/subscribers/{sub_id}/preview", {})
    assert status == 200 and body["item_count"] == 1 and body["reason"] is None
    assert resolve(ctx, "/api/subscribers/not-an-id/preview", {})[0] == 400
    assert resolve(ctx, f"/api/subscribers/{'0' * 16}/preview", {})[0] == 404
    assert resolve(ctx, "/api/preferences/options", {})[1]["weekly_day"] == 3
    assert resolve(ctx, "/api/preferences/options", {})[1]["detail_levels"] == ["brief", "complete"]


def test_preview_without_edition_says_so(tmp_path) -> None:
    config = make_config()
    preview = PreviewService(ItemArchive(tmp_path / "a.sqlite3"), config, {}).preview(
        Subscriber(email="a@example.com")
    )

    assert preview["reason"] == "no_edition" and preview["html"] is None and preview["empty"] is True
    assert preview["would_send"] is False


def test_email_keeps_the_quote_and_the_table_of_contents_as_html() -> None:
    from lucidnews.newsletter.render import render_email

    md = "# Title\n\n> Intro line\n\n---\n\n**Group**\n1. [A](https://example.com/a) 9/10\n2. [B](https://example.com/b) 8/10\n"

    html = render_email(md, language="en", sender_name="LucidNews", unsubscribe_keyword="UNSUBSCRIBE").html

    assert "<blockquote>" in html and "&gt; Intro" not in html
    assert html.count("<li>") == 2 and "<ol>" in html
