import asyncio
import json
from datetime import datetime, timezone
from io import StringIO
from types import SimpleNamespace

import pytest
from pydantic import ValidationError
from rich.console import Console

from src.models import (
    ClassificationResult,
    ContentAnalysis,
    ContentItem,
    ProcessingResult,
    SourceType,
)
from src.newsletter import (
    PLAN_LIMITS,
    DigestPreferences,
    Frequency,
    Plan,
    PlanLimits,
    Subscriber,
    SubscriberStore,
    effective_preferences,
    plan_deliveries,
    select_items,
)
from src.orchestrator import PipelineOrchestrator
from src.reliability import ReliabilityAssessment
from src.storage.manager import StorageManager


def make_item(item_id, score, categories, label="confirmed", source=SourceType.RSS, **metadata):
    return ContentItem(
        id=item_id,
        source_type=source,
        title=item_id,
        url=f"https://example.com/{item_id}",
        published_at=datetime(2026, 10, 5, tzinfo=timezone.utc),
        metadata=metadata,
        processing=ProcessingResult(
            classification=ClassificationResult(profile="tech-news", method="ai_match"),
            analysis=ContentAnalysis(
                score=score, reason="r", summary=f"{item_id} summary", categories=categories
            ),
            reliability=ReliabilityAssessment(label=label, source_tier="official"),
        ),
    )


ITEMS = [
    make_item("llm-release", 9.2, ["ai"], feed_name="OpenAI Blog"),
    make_item("cve", 8.0, ["cybersecurity"], source=SourceType.HACKERNEWS),
    make_item("leak", 7.5, ["ai"], label="rumor"),
    make_item("db-minor", 5.0, ["databases"]),
]


def ids(items):
    return [item.id for item in items]


def test_default_preferences_select_everything_in_order() -> None:
    assert ids(select_items(ITEMS, DigestPreferences())) == ids(ITEMS)


def test_preferences_filter_by_category_importance_reliability_source_and_cap() -> None:
    assert ids(select_items(ITEMS, DigestPreferences(categories=["LLM"]))) == ["llm-release", "leak"]
    assert ids(select_items(ITEMS, DigestPreferences(min_importance="high"))) == [
        "llm-release",
        "cve",
        "leak",
    ]
    assert "leak" not in ids(select_items(ITEMS, DigestPreferences(include_unconfirmed=False)))
    assert ids(select_items(ITEMS, DigestPreferences(sources=["hackernews"]))) == ["cve"]
    assert ids(select_items(ITEMS, DigestPreferences(sources=["openai blog"]))) == ["llm-release"]
    assert ids(select_items(ITEMS, DigestPreferences(max_items=2))) == ["llm-release", "cve"]


def test_preferences_reject_unknown_categories_and_bad_emails() -> None:
    with pytest.raises(ValidationError):
        DigestPreferences(categories=["finance"])
    with pytest.raises(ValidationError):
        Subscriber(email="not-an-email")


def test_plan_limits_hook_clamps_preferences(monkeypatch) -> None:
    subscriber = Subscriber(
        email="a@example.com",
        preferences=DigestPreferences(categories=["ai", "web", "cloud"], frequency="weekly"),
    )
    assert effective_preferences(subscriber) == subscriber.preferences

    monkeypatch.setitem(
        PLAN_LIMITS,
        Plan.FREE,
        PlanLimits(max_categories=1, max_items=5, frequencies=frozenset({Frequency.DAILY})),
    )
    clamped = effective_preferences(subscriber)
    assert clamped.categories == ("ai",)
    assert clamped.max_items == 5
    assert clamped.frequency is Frequency.DAILY


def test_plan_deliveries_groups_identical_preferences_and_falls_back_language() -> None:
    subscribers = [
        Subscriber(email="en1@example.com"),
        Subscriber(email="en2@example.com"),
        Subscriber(email="fr@example.com", preferences=DigestPreferences(language="fr", categories=["ai"])),
        Subscriber(email="de@example.com", preferences=DigestPreferences(language="de")),
        Subscriber(email="weekly@example.com", preferences=DigestPreferences(frequency="weekly")),
    ]

    plan = plan_deliveries(subscribers, ITEMS, ["en", "fr"])

    by_recipients = {tuple(d.recipients): d for d in plan.deliveries}
    assert set(by_recipients) == {
        ("en1@example.com", "en2@example.com", "de@example.com"),
        ("fr@example.com",),
    }
    assert ids(by_recipients[("fr@example.com",)].items) == ["llm-release", "leak"]
    assert plan.language_fallbacks == {"de@example.com": ("de", "en")}
    assert plan.skipped_weekly == ["weekly@example.com"]


def test_store_migrates_legacy_list_and_round_trips(tmp_path) -> None:
    path = tmp_path / "subscribers.json"
    path.write_text(json.dumps(["a@example.com", "A@example.com", "bad"]), encoding="utf-8")
    store = SubscriberStore(path)

    assert [s.email for s in store.load()] == ["a@example.com"]

    store.add("b@example.com", DigestPreferences(language="fr"))
    store.add("b@example.com", DigestPreferences(language="fr", categories=["web"]))
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["version"] == 1
    assert [s["email"] for s in saved["subscribers"]] == ["a@example.com", "b@example.com"]
    assert store.get("B@example.com").preferences.categories == ("web",)

    assert store.remove("a@example.com") is True
    assert store.remove("missing@example.com") is False
    assert [s.email for s in store.load()] == ["b@example.com"]


def test_storage_manager_keeps_email_list_api(tmp_path) -> None:
    storage = StorageManager(data_dir=str(tmp_path))
    storage.add_subscriber("reader@example.com")
    storage.add_subscriber("reader@example.com")

    assert storage.load_subscribers() == ["reader@example.com"]
    storage.remove_subscriber("reader@example.com")
    assert storage.load_subscribers() == []


def test_orchestrator_sends_one_localized_digest_per_preference_group(tmp_path) -> None:
    storage = StorageManager(data_dir=str(tmp_path))
    storage.subscribers.add("en@example.com")
    storage.subscribers.add("fr@example.com", DigestPreferences(language="fr", categories=["cybersecurity"]))
    sent = []

    orchestrator = PipelineOrchestrator.__new__(PipelineOrchestrator)
    orchestrator.console = Console(file=StringIO())
    orchestrator.storage = storage
    orchestrator.icons = PipelineOrchestrator.icons
    orchestrator.profiles = SimpleNamespace(names={})
    orchestrator.config = SimpleNamespace(
        ai=SimpleNamespace(languages=["en", "fr"]),
        digest=SimpleNamespace(profile_order=[]),
    )
    orchestrator.email_manager = SimpleNamespace(
        send_daily_summary=lambda summary, subject, recipients: sent.append((summary, subject, recipients))
    )

    asyncio.run(orchestrator.send_newsletters(ITEMS, "2026-10-05", 118))

    assert [(subject, recipients) for _, subject, recipients in sent] == [
        ("LucidNews — 2026-10-05", ["en@example.com"]),
        ("LucidNews — 2026-10-05", ["fr@example.com"]),
    ]
    fr_summary = sent[1][0]
    assert fr_summary.startswith("# LucidNews Quotidien")
    assert "cve" in fr_summary and "llm-release" not in fr_summary
