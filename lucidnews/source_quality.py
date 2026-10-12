"""Source quality score: how useful and how trustworthy a source's items have been.

Computed from the archive, per source key (see ``source_health.source_key``), over
the items the AI analyzed in a recent window:

- usefulness: mean AI score of its items, on 0..1;
- trust: share of its items labelled "confirmed" or "reliable".

quality = mean of the two, pulled toward 0.5 while a source has few items
(``PRIOR_WEIGHT`` virtual items), so one lucky or unlucky item does not decide.

The digest uses it **only to break ties** between items of equal AI score: it
never puts an item above one with a better score.
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING, Dict, Iterable, Optional

from .models import ContentItem
from .reliability import ReliabilityLabel
from .source_health import source_key

if TYPE_CHECKING:
    from .reliability.assess import ReliabilityPolicy

PRIOR = 0.5
PRIOR_WEIGHT = 5
DEFAULT_DAYS = 30
_TRUSTED = {ReliabilityLabel.CONFIRMED, ReliabilityLabel.RELIABLE}


@dataclass(frozen=True)
class SourceQuality:
    source_key: str
    items: int  # analyzed items in the window
    mean_score: float  # 0..10
    trusted_share: float  # 0..1
    score: float  # 0..1, smoothed


def item_source_key(item: ContentItem) -> str:
    return item.metadata.get("source_key") or source_key(item)


def compute_source_quality(
    items: Iterable[ContentItem], policy: Optional["ReliabilityPolicy"] = None
) -> Dict[str, SourceQuality]:
    """Quality per source key from analyzed items (unscored items are ignored).

    With ``policy``, labels are recomputed with the current trust registry instead
    of the labels stored when each item was published.
    """
    from .reliability.assess import assess_item

    scores: Dict[str, list[float]] = {}
    trusted: Dict[str, int] = {}
    for item in items:
        processing = item.processing
        analysis = processing.analysis if processing else None
        if analysis is None or analysis.score is None:
            continue
        key = item_source_key(item)
        scores.setdefault(key, []).append(analysis.score)
        reliability = assess_item(item, policy) if policy is not None else processing.reliability
        trusted[key] = trusted.get(key, 0) + int(bool(reliability and reliability.label in _TRUSTED))

    result: Dict[str, SourceQuality] = {}
    for key, values in scores.items():
        count = len(values)
        mean_score = sum(values) / count
        trusted_share = trusted[key] / count
        raw = (mean_score / 10 + trusted_share) / 2
        result[key] = SourceQuality(
            source_key=key,
            items=count,
            mean_score=round(mean_score, 2),
            trusted_share=round(trusted_share, 4),
            score=round((count * raw + PRIOR_WEIGHT * PRIOR) / (count + PRIOR_WEIGHT), 4),
        )
    return result


def quality_to_dict(quality: Optional[SourceQuality]) -> Optional[Dict[str, object]]:
    if quality is None:
        return None
    return {
        "score": quality.score,
        "items": quality.items,
        "mean_score": quality.mean_score,
        "trusted_share": quality.trusted_share,
    }
