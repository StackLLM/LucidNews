"""Select digest items for one subscriber's preferences."""

from typing import Iterable, List

from ..models import ContentItem
from ..reliability import UNCONFIRMED_LABELS
from ..taxonomy import importance_at_least, importance_from_score
from .models import DigestPreferences


def _source_keys(item: ContentItem) -> set[str]:
    keys = {item.source_type.value}
    keys.update(item.metadata.get("merged_sources") or [])
    for field in ("feed_name", "subreddit", "channel", "repo"):
        value = item.metadata.get(field)
        if value:
            keys.add(str(value))
    return {key.lower() for key in keys}


def matches(item: ContentItem, prefs: DigestPreferences) -> bool:
    processing = item.processing
    analysis = processing.analysis if processing else None
    if analysis is None or analysis.score is None:
        return False
    if prefs.categories and not set(prefs.categories) & set(analysis.categories):
        return False
    if prefs.sources and not {s.lower() for s in prefs.sources} & _source_keys(item):
        return False
    if prefs.min_importance is not None and not importance_at_least(
        importance_from_score(analysis.score), prefs.min_importance
    ):
        return False
    reliability = processing.reliability if processing else None
    if (
        not prefs.include_unconfirmed
        and (reliability is None or reliability.label in UNCONFIRMED_LABELS)
    ):
        return False
    return True


def select_items(items: Iterable[ContentItem], prefs: DigestPreferences) -> List[ContentItem]:
    """Keep matching items in their existing (score-sorted) order, capped at max_items."""
    selected = [item for item in items if matches(item, prefs)]
    if prefs.max_items is not None:
        selected = selected[: prefs.max_items]
    return selected


def matches_unanalyzed(item: ContentItem, prefs: DigestPreferences) -> bool:
    """Whether an item the AI could not analyze (quota) fits the preferences.

    Without analysis there is no category, importance or claim check, so only a
    subscriber who filters on none of these and accepts unconfirmed news gets it.
    """
    if not (item.processing and item.processing.ai_skipped):
        return False
    if not prefs.include_unconfirmed or prefs.categories or prefs.min_importance is not None:
        return False
    return not prefs.sources or bool({s.lower() for s in prefs.sources} & _source_keys(item))


def select_unanalyzed(
    items: Iterable[ContentItem], prefs: DigestPreferences, already: int = 0
) -> List[ContentItem]:
    """Unanalyzed items for these preferences, within what max_items leaves after ``already``."""
    selected = [item for item in items if matches_unanalyzed(item, prefs)]
    if prefs.max_items is not None:
        selected = selected[: max(0, prefs.max_items - already)]
    return selected
