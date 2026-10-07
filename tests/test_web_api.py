import json
import threading
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from http.server import ThreadingHTTPServer

from src.archive import ItemArchive
from src.models import (
    ClassificationResult,
    ContentAnalysis,
    ContentArtifact,
    ContentBlock,
    ContentItem,
    ProcessingResult,
    SourceType,
)
from src.reliability.assess import assess_item
from src.web_api import ApiContext, make_handler, resolve

NOW = datetime(2026, 10, 6, 12, 0, tzinfo=timezone.utc)


def make_item(item_id: str, profile: str, score: float, *, french: bool = True) -> ContentItem:
    artifacts = {
        "en": ContentArtifact(
            language="en",
            title=f"{item_id} EN",
            blocks=[
                ContentBlock(id="summary", title="Summary", content=f"{item_id} summary", primary=True),
                ContentBlock(id="background", title="Background", content="context"),
            ],
        )
    }
    if french:
        artifacts["fr"] = ContentArtifact(
            language="fr",
            title=f"{item_id} FR",
            blocks=[ContentBlock(id="summary", title="Résumé", content=f"{item_id} résumé", primary=True)],
        )
    item = ContentItem(
        id=item_id,
        source_type=SourceType.HACKERNEWS,
        title=f"{item_id} original",
        url=f"https://lwn.net/{item_id}",
        published_at=NOW - timedelta(hours=1),
        metadata={"discussion_url": f"https://news.ycombinator.com/item?id={item_id}"},
        processing=ProcessingResult(
            classification=ClassificationResult(profile=profile, method="ai_match"),
            analysis=ContentAnalysis(score=score, reason="r", summary="analysis summary", categories=["web"]),
            artifacts=artifacts,
        ),
    )
    item.processing.reliability = assess_item(item)
    return item


def make_context(tmp_path) -> tuple[ApiContext, str]:
    archive = ItemArchive(tmp_path / "archive.sqlite3")
    run_id = archive.start_run(NOW - timedelta(hours=24))
    archive.record_items(run_id, [make_item("dropped", "tech-news", 3.0)])
    archive.record_items(
        run_id,
        [
            make_item("blog", "tech-blog", 9.0),
            make_item("low", "tech-news", 7.0, french=False),
            make_item("top", "tech-news", 9.5),
        ],
        selected=True,
    )
    archive.finish_run(run_id, "success")
    ctx = ApiContext(
        archive=archive,
        profile_names={"tech-news": {"default": "Technology News", "fr": "Actualités tech"}},
        profile_order=["tech-news", "tech-blog"],
    )
    return ctx, run_id


def test_latest_edition_groups_selected_items_in_profile_order(tmp_path) -> None:
    ctx, run_id = make_context(tmp_path)

    status, body = resolve(ctx, "/api/editions/latest", {"lang": ["fr"]})

    assert status == 200
    assert (body["id"], body["fetched_count"], body["selected_count"]) == (run_id, 4, 3)
    assert body["available_languages"] == ["en", "fr"]
    assert [(s["profile"], s["name"]) for s in body["sections"]] == [
        ("tech-news", "Actualités tech"),
        ("tech-blog", "Tech Blog"),
    ]
    top, low = body["sections"][0]["items"]
    assert (top["title"], top["summary"], top["importance"]) == ("top FR", "top résumé", "critical")
    assert top["reliability"]["label"] == "reliable"
    assert top["discussion_url"] == "https://news.ycombinator.com/item?id=top"
    # No French artifact: original title and analysis summary, flagged as untranslated.
    assert (low["title"], low["summary"], low["translated"]) == ("low original", "analysis summary", False)


def test_edition_by_id_and_errors(tmp_path) -> None:
    ctx, run_id = make_context(tmp_path)

    status, body = resolve(ctx, f"/api/editions/{run_id}", {})
    assert status == 200
    assert body["sections"][0]["items"][0]["sections"] == [
        {"id": "background", "title": "Background", "content": "context"}
    ]
    assert resolve(ctx, "/api/editions", {})[1]["editions"][0]["id"] == run_id
    assert resolve(ctx, "/api/editions/../../etc", {})[0] == 400
    assert resolve(ctx, "/api/editions/20990101T000000Z-00000000", {})[0] == 404
    assert resolve(ctx, "/api/editions/latest", {"lang": ["xx"]})[0] == 400
    assert resolve(ctx, "/api/unknown", {})[0] == 404


def test_http_server_serves_json(tmp_path) -> None:
    ctx, _ = make_context(tmp_path)
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(ctx))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        with urllib.request.urlopen(f"{base}/api/editions/latest?lang=fr") as response:
            assert response.headers["Content-Type"] == "application/json; charset=utf-8"
            assert json.loads(response.read())["sections"][0]["name"] == "Actualités tech"
        try:
            urllib.request.urlopen(f"{base}/api/nope")
        except urllib.error.HTTPError as error:
            assert error.code == 404
    finally:
        server.shutdown()
        server.server_close()


def test_sources_endpoint_reports_configured_sources_and_runs(tmp_path) -> None:
    from src.source_health import SourceRunOutcome

    ctx, run_id = make_context(tmp_path)
    ctx.configured_sources = {"rss/Kept": "rss", "rss/New": "rss"}
    ctx.archive.record_source_runs(
        run_id,
        [
            SourceRunOutcome("rss/Kept", "rss", "failure", error="HTTPStatusError: 404"),
            SourceRunOutcome("rss/Removed", "rss", "success", fetched_count=4),
        ],
    )

    status, body = resolve(ctx, "/api/sources", {"days": ["7"]})

    assert status == 200
    assert [(s["source"], s["status"], s["last_error"]) for s in body["sources"]] == [
        ("rss/Kept", "failing", "HTTPStatusError: 404")
    ]
    assert body["configured_without_history"] == ["rss/New"]
    assert [(r["id"], r["fetched_count"], r["selected_count"]) for r in body["runs"]] == [(run_id, 4, 3)]
    assert resolve(ctx, "/api/sources", {"days": ["0"]})[0] == 400
    assert resolve(ctx, "/api/sources", {"days": ["abc"]})[0] == 400
