import json
from datetime import datetime, timezone

import pytest

from lucidnews.archive import ItemArchive
from lucidnews.evaluation import Annotation, AnnotationStore, evaluate
from lucidnews.evaluation.cli import main as eval_main
from lucidnews.evaluation.metrics import pipeline_selection_rule
from lucidnews.evaluation.service import EvaluationService, excerpt
from lucidnews.models import ClassificationResult, ContentAnalysis, ContentItem, ProcessingResult, SourceType
from lucidnews.reliability.assess import assess_item
from lucidnews.web_api import ApiContext, resolve, resolve_write

NOW = datetime(2026, 10, 6, 12, 0, tzinfo=timezone.utc)


def make_item(item_id: str, url: str, score: float, claim: str, categories=("ai",), profile="tech-news") -> ContentItem:
    item = ContentItem(
        id=item_id,
        source_type=SourceType.HACKERNEWS,
        title=f"{item_id} title",
        url=url,
        content="<p>Body &amp; facts</p>\n\n--- Top Comments ---\n\n[x]: comment",
        published_at=NOW,
        processing=ProcessingResult(
            classification=ClassificationResult(profile=profile, method="ai_match"),
            analysis=ContentAnalysis.model_validate(
                {"score": score, "reason": "r", "summary": "s", "categories": list(categories),
                 "claim": {"status": claim, "evidence": "e"}}
            ),
        ),
    )
    item.processing.reliability = assess_item(item)
    return item


ITEMS = {
    # Official source, AI and human agree.
    "official": make_item("official", "https://openai.com/index/x", 9.0, "confirmed"),
    # Reputable outlet: AI says reported (-> reliable); human says rumor (-> rumor): false reliable.
    "leak": make_item("leak", "https://theverge.com/x", 8.0, "reported", ("ai", "cloud")),
    # Below threshold, community source.
    "minor": make_item("minor", "https://news.ycombinator.com/item?id=1", 4.0, "unverified", ("web",)),
}

ANNOTATIONS = {
    "official": Annotation(item_id="official", relevant=True, importance="critical", categories=["ai"], claim_status="confirmed"),
    "leak": Annotation(item_id="leak", relevant=True, importance="medium", categories=["ai"], claim_status="rumor"),
    "minor": Annotation(item_id="minor", relevant=True, importance="medium", categories=["web"], claim_status="unverified"),
    "gone": Annotation(item_id="gone", relevant=False, importance="low", claim_status="unverified"),
}


def test_metrics_cover_selection_importance_categories_and_reliability() -> None:
    rule = pipeline_selection_rule({"tech-news": 7.0})
    report = evaluate(ANNOTATIONS, ITEMS, rule).to_dict()

    assert (report["annotated"], report["compared"], report["missing"]) == (4, 3, ["gone"])
    assert report["small_sample"] is True
    # official + leak selected (>= 7), minor not; all three relevant for the human.
    selection = report["selection"]
    assert (selection["true_positive"], selection["false_negative"], selection["false_positive"]) == (2, 1, 0)
    assert selection["precision"] == 1.0
    assert report["selection"]["recall"] == pytest.approx(0.6667)
    # critical=critical, high vs medium (1 band), low vs medium (1 band)
    assert (report["importance"]["exact"], report["importance"]["within_one"]) == (pytest.approx(0.3333), 1.0)
    # 3 correct categories out of 4 predicted and 3 expected
    assert (report["categories"]["precision"], report["categories"]["recall"]) == (0.75, 1.0)
    assert report["claim"]["accuracy"] == pytest.approx(0.6667)
    assert report["claim"]["overconfident"] == 1
    assert report["claim"]["confusion"]["rumor"]["reported"] == 1
    assert report["reliability"]["false_reliable_items"] == ["leak"]
    leak = next(item for item in report["items"] if item["item_id"] == "leak")
    assert leak["issues"] == ["importance", "categories", "claim", "false_reliable"]
    assert (leak["ai"]["reliability"], leak["human"]["reliability"]) == ("reliable", "rumor")


def test_annotation_validates_categories_and_caps_at_three() -> None:
    with pytest.raises(ValueError):
        Annotation(item_id="x", relevant=True, importance="high", categories=["gardening"], claim_status="confirmed")
    annotation = Annotation(
        item_id="x", relevant=True, importance="high", claim_status="confirmed",
        categories=["security", "ai", "web", "cloud"],
    )
    assert annotation.categories == ["cybersecurity", "ai", "web"]


def test_excerpt_is_plain_text_without_ai_output() -> None:
    assert excerpt(ITEMS["official"]) == "Body & facts"


@pytest.fixture
def service(tmp_path) -> EvaluationService:
    archive = ItemArchive(tmp_path / "archive.sqlite3")
    run_id = archive.start_run(NOW)
    archive.record_items(run_id, ITEMS.values())
    archive.finish_run(run_id, "success")
    return EvaluationService(
        archive, AnnotationStore(tmp_path / "eval" / "annotations.json"), pipeline_selection_rule({"tech-news": 7.0})
    )


def test_api_serves_blind_candidates_and_saves_annotations(service, tmp_path) -> None:
    ctx = ApiContext(archive=service.archive, evaluation=service)

    status, body = resolve(ctx, "/api/eval/items", {})
    assert status == 200
    assert sorted(item["id"] for item in body["items"]) == ["leak", "minor", "official"]
    # Blind: nothing from the AI analysis is exposed while annotating.
    assert set(body["items"][0]) == {
        "id", "title", "url", "source_type", "source", "author", "published_at", "excerpt", "discussion_url", "annotation",
    }

    payload = {"relevant": True, "importance": "high", "categories": ["ai"], "claim_status": "reported", "notes": "ok"}
    status, saved = resolve_write(ctx, "PUT", "/api/eval/annotations/leak", payload)
    assert status == 200
    assert (saved["title"], saved["url"]) == ("leak title", "https://theverge.com/x")
    assert resolve(ctx, "/api/eval/items", {})[1]["annotated"] == 1
    assert json.loads((tmp_path / "eval" / "annotations.json").read_text())["annotations"][0]["item_id"] == "leak"

    assert resolve(ctx, "/api/eval/report", {})[1]["compared"] == 1
    assert "importance" in resolve_write(ctx, "PUT", "/api/eval/annotations/leak", {**payload, "importance": "huge"})[1]["fields"]
    assert resolve_write(ctx, "PUT", "/api/eval/annotations/missing", payload)[0] == 404
    assert resolve_write(ctx, "DELETE", "/api/eval/annotations/leak", {})[0] == 200
    assert resolve_write(ctx, "DELETE", "/api/eval/annotations/leak", {})[0] == 404


def test_eval_routes_are_off_without_local_features(tmp_path) -> None:
    ctx = ApiContext(archive=ItemArchive(tmp_path / "a.sqlite3"))
    assert resolve(ctx, "/api/eval/items", {})[0] == 403
    assert resolve_write(ctx, "PUT", "/api/eval/annotations/x", {})[0] == 403


def test_cli_reports_and_compares_with_previous_run(tmp_path, capsys) -> None:
    (tmp_path / "config.json").write_text(json.dumps({
        "ai": {"provider": "openai", "model": "m", "api_key_env": "K"},
        "sources": {"hackernews": {"enabled": False}},
        "processing": {"profile_settings": {"tech-news": {"threshold": 7.0}}},
    }))
    archive = ItemArchive(tmp_path / "archive.sqlite3")
    run_id = archive.start_run(NOW)
    archive.record_items(run_id, ITEMS.values())
    store = AnnotationStore(tmp_path / "eval" / "annotations.json")
    for annotation in ANNOTATIONS.values():
        store.upsert(annotation)

    assert eval_main(["--data-dir", str(tmp_path), "--json"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert (report["mode"], report["reliability"]["false_reliable"]) == ("stored", 1)
    assert len(list((tmp_path / "eval" / "reports").glob("*-stored.json"))) == 1

    assert eval_main(["--data-dir", str(tmp_path), "--no-save"]) == 0
    out = capsys.readouterr().out
    assert "False reliable" in out and "leak title" in out


def test_cli_without_annotations_explains_what_to_do(tmp_path, capsys) -> None:
    (tmp_path / "config.json").write_text(json.dumps({
        "ai": {"provider": "openai", "model": "m", "api_key_env": "K"}, "sources": {"hackernews": {"enabled": False}},
    }))
    ItemArchive(tmp_path / "archive.sqlite3")
    assert eval_main(["--data-dir", str(tmp_path)]) == 1
    assert "No annotation yet" in capsys.readouterr().out


def test_cli_rerun_reanalyzes_annotated_items_with_current_prompts(tmp_path, capsys, monkeypatch) -> None:
    (tmp_path / "config.json").write_text(json.dumps({
        "ai": {"provider": "openai", "model": "m", "api_key_env": "K"},
        "sources": {"hackernews": {"enabled": False}},
        "processing": {"profile_settings": {"tech-news": {"threshold": 7.0}}},
    }))
    archive = ItemArchive(tmp_path / "archive.sqlite3")
    archive.record_items(archive.start_run(NOW), ITEMS.values())
    AnnotationStore(tmp_path / "eval" / "annotations.json").upsert(ANNOTATIONS["leak"])
    seen = []

    class FakeAnalyzer:
        def __init__(self, *args, **kwargs):
            pass

        async def analyze_batch(self, items):
            for item in items:
                seen.append((item.id, item.processing.analysis, item.processing.reliability))
                # A "better prompt": the leak is now judged a rumor.
                item.processing.analysis = ContentAnalysis.model_validate(
                    {"score": 6.0, "reason": "r", "summary": "s", "categories": ["ai"],
                     "claim": {"status": "rumor", "evidence": "anonymous"}}
                )
            return items

    monkeypatch.setattr("lucidnews.ai.analyzer.ContentAnalyzer", FakeAnalyzer)
    monkeypatch.setattr("lucidnews.ai.client.create_ai_client", lambda config: object())

    assert eval_main(["--data-dir", str(tmp_path), "--rerun", "--json"]) == 0
    report = json.loads(capsys.readouterr().out)

    assert seen == [("leak", None, None)]  # previous analysis and label dropped before re-analysis
    assert (report["mode"], report["model"]) == ("rerun", "openai/m")
    assert report["reliability"]["false_reliable"] == 0
    assert report["claim"]["accuracy"] == 1.0
    # The stored analysis in the archive is untouched.
    assert archive.get_item("leak").processing.analysis.claim.status.value == "reported"
