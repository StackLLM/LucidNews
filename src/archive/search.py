"""Full-text search over the archive (SQLite FTS5), fed when items are recorded.

What is indexed, per analyzed item: the original title, the localized titles, the AI
summary, the tags, the author and the text of every enrichment block, in every language
produced. The raw article body is not indexed (long, noisy). Accents and case are ignored
and each word matches as a prefix (``kuber`` finds ``Kubernetes``).

The search never builds SQL from the query: it is cut into plain words, each quoted for
FTS5, so operators and punctuation typed by the reader cannot change its meaning.
"""

import re
import sqlite3
from typing import Iterable, List, Optional, Sequence, Tuple

from ..models import ContentItem

MAX_QUERY_LENGTH = 200
MAX_TERMS = 10
MIN_TERM_LENGTH = 2
CANDIDATE_CAP = 1000  # matches considered per query, best first
INDEX_VERSION = "1"

FTS_SCHEMA = """
CREATE VIRTUAL TABLE IF NOT EXISTS items_fts USING fts5(
    item_id UNINDEXED, title, body, tokenize = "unicode61 remove_diacritics 2"
)
"""

_WORD = re.compile(r"[\w][\w'’-]*", re.UNICODE)


class SearchQueryError(ValueError):
    """The query is empty, too long or has no usable word."""


def search_terms(query: str) -> List[str]:
    """The words of a query, in order, without duplicates."""
    if not isinstance(query, str) or not query.strip():
        raise SearchQueryError("query is empty")
    if len(query) > MAX_QUERY_LENGTH:
        raise SearchQueryError(f"query is longer than {MAX_QUERY_LENGTH} characters")
    terms: List[str] = []
    for match in _WORD.finditer(query):
        word = match.group(0).strip("'’-")
        if len(word) >= MIN_TERM_LENGTH and word.lower() not in (t.lower() for t in terms):
            terms.append(word)
    if not terms:
        raise SearchQueryError(f"no word of at least {MIN_TERM_LENGTH} characters")
    if len(terms) > MAX_TERMS:
        raise SearchQueryError(f"more than {MAX_TERMS} words")
    return terms


def match_expression(terms: Sequence[str]) -> str:
    """FTS5 expression: every word, as a quoted prefix. Quotes inside a word are doubled."""
    return " ".join('"' + term.replace('"', '""') + '"*' for term in terms)


def index_text(item: ContentItem) -> Optional[Tuple[str, str]]:
    """(title text, body text) to index, or None for an item that is not analyzed."""
    processing = item.processing
    if processing is None:
        return None
    analysis = processing.analysis
    if (analysis is None or analysis.score is None) and processing.ai_skipped is None:
        return None  # not searchable: the item page does not exist for it either
    titles = [item.title] + [artifact.title for artifact in processing.artifacts.values()]
    parts: List[str] = []
    if analysis is not None:
        parts.append(analysis.summary or "")
        parts.extend(analysis.tags)
    if item.author:
        parts.append(item.author)
    for artifact in processing.artifacts.values():
        for block in artifact.blocks:
            parts.append(block.title)
            parts.append(block.content)
    return " \n".join(dict.fromkeys(title for title in titles if title)), " \n".join(part for part in parts if part)


def reindex(conn: sqlite3.Connection, items: Iterable[ContentItem]) -> int:
    """Replace the index rows of ``items`` (inside the caller's transaction)."""
    count = 0
    for item in items:
        conn.execute("DELETE FROM items_fts WHERE item_id = ?", (item.id,))
        text = index_text(item)
        if text is None:
            continue
        conn.execute("INSERT INTO items_fts (item_id, title, body) VALUES (?, ?, ?)", (item.id, *text))
        count += 1
    return count


def rebuild(conn: sqlite3.Connection) -> int:
    """Index every archived item again (first use of search on an existing archive)."""
    conn.execute("DELETE FROM items_fts")
    count = 0
    cursor = conn.execute("SELECT payload FROM items")
    while rows := cursor.fetchmany(500):
        count += reindex(conn, (ContentItem.model_validate_json(row["payload"]) for row in rows))
    conn.execute("INSERT OR REPLACE INTO meta (key, value) VALUES ('fts_version', ?)", (INDEX_VERSION,))
    return count
