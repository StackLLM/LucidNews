"""Lot 23: full-text search of the archive."""

import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from lucidnews.archive import ItemArchive
from lucidnews.archive.search import SearchQueryError, match_expression, search_terms
from lucidnews.models import (
    ClassificationResult,
    ContentAnalysis,
    ContentArtifact,
    ContentBlock,
    ContentItem,
    ProcessingResult,
    SourceType,
)
from lucidnews.reliability import ReliabilityAssessment
from lucidnews.web_api import ApiContext, resolve

NOW = datetime(2026, 10, 11, 9, 0, tzinfo=timezone.utc)


def make_item(item_id, title, summary="a summary", *, categories=("web",), label="confirmed", feed="Feed A", score=8.0, fr_title=None, tags=(), block=None, analyzed=True):
    artifacts = {}
    if fr_title or block:
        artifacts["fr"] = ContentArtifact(
            language="fr",
            title=fr_title or title,
            blocks=[ContentBlock(id="lead", title="Résumé", content=block or summary, primary=True)],
        )
    return ContentItem(
        id=item_id,
        source_type=SourceType.RSS,
        title=title,
        url=f"https://example.com/{item_id}",
        published_at=NOW - timedelta(hours=1),
        metadata={"feed_name": feed},
        processing=ProcessingResult(
            classification=ClassificationResult(profile="tech-news", method="ai_match"),
            analysis=ContentAnalysis(score=score, reason="r", summary=summary, categories=list(categories), tags=list(tags)) if analyzed else None,
            reliability=ReliabilityAssessment(label=label, source_tier="official") if analyzed else None,
            artifacts=artifacts,
        ),
    )


@pytest.fixture
def archive(tmp_path) -> ItemArchive:
    archive = ItemArchive(tmp_path / "archive.sqlite3")
    run = archive.start_run(NOW - timedelta(days=1))
    archive.record_items(
        run,
        [
            make_item("k8s", "Kubernetes 1.32 released", "Faster scheduling in the control plane", categories=("cloud", "devops"), feed="K8s Blog", tags=("containers",)),
            make_item("eco", "Python tooling", "Un écosystème de paquets plus rapide", categories=("software-development",), fr_title="L'outillage Python", block="Le nouvel écosystème d'outils accélère les installations", feed="Feed B"),
            make_item("rumor", "Rumored chip delay", "Unconfirmed report about a chip", categories=("emerging-tech",), label="rumor", feed="Feed A"),
            make_item("raw", "Kubernetes raw item, never analyzed", analyzed=False),
        ],
    )
    archive.record_items(run, [make_item("k8s", "Kubernetes 1.32 released", "Faster scheduling in the control plane", categories=("cloud", "devops"), feed="K8s Blog", tags=("containers",))], selected=True)
    archive.finish_run(run, "success")
    return archive


def ids(archive, query):
    return [item.id for item, _ in archive.search(search_terms(query))]


# --- The query ---------------------------------------------------------------------------------


def test_a_query_is_cut_into_plain_words() -> None:
    assert search_terms("  Kubernetes   scheduling ") == ["Kubernetes", "scheduling"]
    assert search_terms("l'outillage c++ AND (a OR b) NEAR/2 \"x*\" -foo") == ["l'outillage", "AND", "OR", "NEAR", "foo"]
    assert search_terms("rust Rust RUST") == ["rust"]
    assert match_expression(["a\"b", "c"]) == '"a""b"* "c"*'


@pytest.mark.parametrize("bad", ["", "   ", "a", "+ - * ()", "x" * 201, " ".join(f"word{n}" for n in range(11))])
def test_an_empty_or_unusable_query_is_refused(bad) -> None:
    with pytest.raises(SearchQueryError):
        search_terms(bad)


# --- What is found -----------------------------------------------------------------------------


def test_title_summary_tags_and_enrichment_text_are_searched(archive) -> None:
    assert ids(archive, "kubernetes") == ["k8s"]  # not the unanalyzed "raw" item
    assert ids(archive, "scheduling plane") == ["k8s"]  # every word, any order
    assert ids(archive, "containers") == ["k8s"]  # tag
    assert ids(archive, "outillage") == ["eco"]  # localized title, other language
    assert ids(archive, "accélère") == ["eco"]  # enrichment block text
    assert ids(archive, "nothingmatchesthis") == []


def test_accents_case_and_prefixes_are_ignored(archive) -> None:
    assert ids(archive, "ECOSYSTEME") == ["eco"]
    assert ids(archive, "écosystème") == ["eco"]
    assert ids(archive, "kuber") == ["k8s"]
    assert ids(archive, "kubernetes released") == ["k8s"]


def test_operators_and_sql_typed_by_the_reader_do_nothing(archive) -> None:
    for hostile in ['"unbalanced', "kubernetes OR python", "NEAR(a b)", "title:kubernetes", "kube*", "'; DROP TABLE items; --", "\\\\ % _ ^"]:
        try:
            ids(archive, hostile)
        except SearchQueryError:
            pass
    assert ids(archive, "kubernetes") == ["k8s"]  # still there, nothing dropped
    assert ids(archive, "kubernetes OR python") == []  # "OR" is a word, not an operator


def test_the_index_follows_the_items(archive) -> None:
    run = archive.start_run(NOW)
    archive.record_items(run, [make_item("k8s", "Kubernetes 1.32 released", "Now about gateways", categories=("cloud",), feed="K8s Blog")])

    assert ids(archive, "scheduling") == []  # the old summary is gone
    assert ids(archive, "gateways") == ["k8s"]


def test_an_existing_archive_is_indexed_when_opened(archive, tmp_path) -> None:
    with sqlite3.connect(archive.path) as conn:
        conn.execute("DROP TABLE items_fts")
        conn.execute("DELETE FROM meta WHERE key = 'fts_version'")

    reopened = ItemArchive(archive.path)

    assert [item.id for item, _ in reopened.search(["kubernetes"])] == ["k8s"]
    # Opening again does not index twice.
    with sqlite3.connect(archive.path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM items_fts WHERE item_id = 'k8s'").fetchone()[0] == 1


# --- The API -----------------------------------------------------------------------------------


def get(archive, **params):
    return resolve(ApiContext(archive=archive), "/api/search", {key: [str(value)] for key, value in params.items()})


def test_the_api_returns_results_with_their_context(archive) -> None:
    status, body = get(archive, q="kubernetes", lang="fr")

    assert status == 200 and body["total"] == 1 and body["terms"] == ["kubernetes"]
    [hit] = body["results"]
    assert hit["id"] == "k8s" and hit["source"] == "rss/K8s Blog" and hit["categories"] == ["cloud", "devops"]
    assert hit["reliability"] == "confirmed" and hit["score"] == 8.0
    assert hit["edition"] is not None and hit["edition_at"] is not None  # it was published
    status, body = get(archive, q="rumored")
    assert body["results"][0]["edition"] is None and body["results"][0]["edition_at"] is None  # analyzed, never published


def test_the_api_shows_the_title_and_summary_in_the_requested_language(archive) -> None:
    fr = get(archive, q="ecosysteme", lang="fr")[1]["results"][0]
    en = get(archive, q="ecosysteme", lang="en")[1]["results"][0]

    assert fr["title"] == "L'outillage Python" and "écosystème" in fr["summary"]
    assert en["title"] == "Python tooling"


def test_filters_narrow_the_results_and_the_counts_ignore_them(archive) -> None:
    everything = get(archive, q="faster OR chip OR released OR python OR rumored")[1]
    only = get(archive, q="chip", label="rumor")[1]
    assert only["total"] == 1 and only["results"][0]["id"] == "rumor"
    assert get(archive, q="chip", label="confirmed")[1]["total"] == 0
    assert get(archive, q="kubernetes", category="devops")[1]["total"] == 1
    assert get(archive, q="kubernetes", category="web")[1]["total"] == 0
    assert get(archive, q="kubernetes", source="rss/K8s Blog")[1]["total"] == 1
    assert get(archive, q="kubernetes", source="rss/Feed A")[1]["total"] == 0
    facets = get(archive, q="faster", category="web")[1]["facets"]
    assert facets["categories"] == {"cloud": 1, "devops": 1}  # counts of the words, not of the filter
    assert facets["labels"] == {"confirmed": 1} and facets["sources"] == [{"source": "rss/K8s Blog", "count": 1}]
    assert everything["total"] == 0  # "OR" is not an operator: all five words are required


def test_results_are_paged(archive) -> None:
    run = archive.start_run(NOW)
    archive.record_items(run, [make_item(f"n{n}", f"Postgres release {n}", "databases news", categories=("databases",)) for n in range(5)])

    first = get(archive, q="postgres", limit=2)[1]
    last = get(archive, q="postgres", limit=2, offset=4)[1]

    assert first["total"] == 5 and len(first["results"]) == 2 and last["total"] == 5 and len(last["results"]) == 1
    assert {hit["id"] for hit in first["results"]}.isdisjoint({hit["id"] for hit in get(archive, q="postgres", limit=2, offset=2)[1]["results"]})
    assert first["truncated"] is False


def test_the_api_refuses_bad_requests_cleanly(archive) -> None:
    for params in (
        {},
        {"q": ""},
        {"q": "x" * 201},
        {"q": "a"},
        {"q": "ok", "category": "finance"},
        {"q": "ok", "label": "certain"},
        {"q": "ok", "limit": 0},
        {"q": "ok", "limit": 101},
        {"q": "ok", "offset": -1},
        {"q": "ok", "limit": "x"},
        {"q": "ok", "source": "bad\x00source"},
    ):
        status, body = get(archive, **params)
        assert status == 400 and "error" in body, params


def test_search_says_so_when_sqlite_has_no_fts(archive) -> None:
    archive.search_available = False

    status, body = get(archive, q="kubernetes")

    assert status == 503 and "FTS5" in body["error"]
