"""Compare the AI analysis of archived items with human annotations.

Four questions, one block each:

- selection: would the pipeline publish the items a human says belong in the edition?
- importance: does the AI's 0-10 score land in the human's importance band?
- categories: does the AI pick the same topics?
- claim / reliability: does the AI judge verification like a human, and, most
  important, does any item end up labelled confirmed/reliable when the human's
  claim judgement would have made it unverified/rumor ("false reliable")?

Everything is computed from data already stored (no AI call), so the numbers are
reproducible and free. ``cli.py --rerun`` re-analyzes with the current prompts
before calling the same function.
"""

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Mapping, Optional, Sequence

from ..models import ContentItem
from ..reliability import ClaimAssessment, ClaimStatus, ReliabilityLabel, UNCONFIRMED_LABELS
from ..reliability.assess import ReliabilityPolicy, assess_item
from ..taxonomy import IMPORTANCE_ORDER, Importance, importance_from_score
from .models import Annotation

CLAIM_ORDER = [ClaimStatus.CONFIRMED, ClaimStatus.REPORTED, ClaimStatus.UNVERIFIED, ClaimStatus.RUMOR]
TRUSTED_LABELS = {ReliabilityLabel.CONFIRMED, ReliabilityLabel.RELIABLE}

# Under this many annotated items, rates swing too much to be read as a trend.
MIN_RELIABLE_SAMPLE = 30

SelectionRule = Callable[[ContentItem], bool]


def _ratio(numerator: float, denominator: float) -> Optional[float]:
    return round(numerator / denominator, 4) if denominator else None


def _f1(precision: Optional[float], recall: Optional[float]) -> Optional[float]:
    if not precision or not recall:
        return 0.0 if precision is not None and recall is not None else None
    return round(2 * precision * recall / (precision + recall), 4)


@dataclass
class ItemComparison:
    item_id: str
    title: str
    human: Annotation
    ai_score: Optional[float]
    ai_selected: bool
    ai_importance: Optional[Importance]
    ai_categories: List[str]
    ai_claim: Optional[ClaimStatus]
    ai_label: Optional[ReliabilityLabel]
    human_label: Optional[ReliabilityLabel]

    @property
    def false_reliable(self) -> bool:
        return (
            self.ai_label in TRUSTED_LABELS
            and self.human_label is not None
            and self.human_label in UNCONFIRMED_LABELS
        )

    @property
    def issues(self) -> List[str]:
        issues = []
        if self.ai_selected != self.human.relevant:
            issues.append("selection")
        if self.ai_importance is not None and self.ai_importance != self.human.importance:
            issues.append("importance")
        if set(self.ai_categories) != set(self.human.categories):
            issues.append("categories")
        if self.ai_claim != self.human.claim_status:
            issues.append("claim")
        if self.false_reliable:
            issues.append("false_reliable")
        return issues

    def to_dict(self) -> Dict[str, object]:
        return {
            "item_id": self.item_id,
            "title": self.title,
            "issues": self.issues,
            "human": {
                "relevant": self.human.relevant,
                "importance": self.human.importance.value,
                "categories": self.human.categories,
                "claim_status": self.human.claim_status.value,
                "reliability": self.human_label.value if self.human_label else None,
                "notes": self.human.notes,
            },
            "ai": {
                "score": self.ai_score,
                "selected": self.ai_selected,
                "importance": self.ai_importance.value if self.ai_importance else None,
                "categories": self.ai_categories,
                "claim_status": self.ai_claim.value if self.ai_claim else None,
                "reliability": self.ai_label.value if self.ai_label else None,
            },
        }


@dataclass
class EvaluationReport:
    annotated: int
    compared: List[ItemComparison] = field(default_factory=list)
    missing: List[str] = field(default_factory=list)  # annotated but absent or unanalyzed in the archive

    def _matrix(self, order: Sequence, human: Callable, ai: Callable) -> Dict[str, Dict[str, int]]:
        matrix = {h.value: {a.value: 0 for a in order} | {"none": 0} for h in order}
        for comparison in self.compared:
            predicted = ai(comparison)
            matrix[human(comparison).value][predicted.value if predicted else "none"] += 1
        return matrix

    def to_dict(self) -> Dict[str, object]:
        compared = self.compared
        n = len(compared)

        tp = sum(c.ai_selected and c.human.relevant for c in compared)
        fp = sum(c.ai_selected and not c.human.relevant for c in compared)
        fn = sum(not c.ai_selected and c.human.relevant for c in compared)
        tn = n - tp - fp - fn
        sel_precision, sel_recall = _ratio(tp, tp + fp), _ratio(tp, tp + fn)

        scored = [c for c in compared if c.ai_importance is not None]
        distance = [
            abs(IMPORTANCE_ORDER.index(c.ai_importance) - IMPORTANCE_ORDER.index(c.human.importance))
            for c in scored
        ]

        cat_tp = sum(len(set(c.ai_categories) & set(c.human.categories)) for c in compared)
        cat_predicted = sum(len(c.ai_categories) for c in compared)
        cat_expected = sum(len(c.human.categories) for c in compared)
        cat_precision, cat_recall = _ratio(cat_tp, cat_predicted), _ratio(cat_tp, cat_expected)

        overconfident = [
            c for c in compared
            if c.human.claim_status in (ClaimStatus.UNVERIFIED, ClaimStatus.RUMOR)
            and c.ai_claim in (ClaimStatus.CONFIRMED, ClaimStatus.REPORTED)
        ]
        false_reliable = [c for c in compared if c.false_reliable]

        return {
            "annotated": self.annotated,
            "compared": n,
            "missing": self.missing,
            "small_sample": n < MIN_RELIABLE_SAMPLE,
            "selection": {
                "true_positive": tp, "false_positive": fp, "false_negative": fn, "true_negative": tn,
                "precision": sel_precision, "recall": sel_recall, "f1": _f1(sel_precision, sel_recall),
                "accuracy": _ratio(tp + tn, n),
            },
            "importance": {
                "exact": _ratio(sum(d == 0 for d in distance), len(scored)),
                "within_one": _ratio(sum(d <= 1 for d in distance), len(scored)),
                "mean_band_error": _ratio(sum(distance), len(scored)),
                "confusion": self._matrix(IMPORTANCE_ORDER, lambda c: c.human.importance, lambda c: c.ai_importance),
            },
            "categories": {
                "precision": cat_precision, "recall": cat_recall, "f1": _f1(cat_precision, cat_recall),
                "exact_match": _ratio(sum(set(c.ai_categories) == set(c.human.categories) for c in compared), n),
            },
            "claim": {
                "accuracy": _ratio(sum(c.ai_claim == c.human.claim_status for c in compared), n),
                "overconfident": len(overconfident),
                "confusion": self._matrix(CLAIM_ORDER, lambda c: c.human.claim_status, lambda c: c.ai_claim),
            },
            "reliability": {
                "agreement": _ratio(sum(c.ai_label == c.human_label for c in compared), n),
                "false_reliable": len(false_reliable),
                "false_reliable_items": [c.item_id for c in false_reliable],
            },
            "items": [c.to_dict() for c in compared],
        }


def pipeline_selection_rule(
    thresholds: Mapping[str, Optional[float]],
    exclude_labels: Sequence[ReliabilityLabel] = (),
) -> SelectionRule:
    """Same decision as ``PipelineOrchestrator.passes_profile_filter`` (score + profile threshold)."""

    def selected(item: ContentItem) -> bool:
        processing = item.processing
        analysis = processing.analysis if processing else None
        if analysis is None or analysis.score is None:
            return False
        if processing.reliability is not None and processing.reliability.label in exclude_labels:
            return False
        threshold = thresholds.get(processing.classification.profile)
        return threshold is None or analysis.score >= threshold

    return selected


def _label_with_claim(item: ContentItem, claim: ClaimStatus, policy: ReliabilityPolicy) -> ReliabilityLabel:
    """The reliability label the item would get if the AI had judged the claim like the human."""
    copy = item.model_copy(deep=True)
    copy.processing.analysis.claim = ClaimAssessment(status=claim, evidence="human annotation")
    return assess_item(copy, policy).label


def evaluate(
    annotations: Mapping[str, Annotation],
    items: Mapping[str, ContentItem],
    selection_rule: SelectionRule,
    policy: Optional[ReliabilityPolicy] = None,
) -> EvaluationReport:
    policy = policy or ReliabilityPolicy()
    report = EvaluationReport(annotated=len(annotations))
    for item_id, annotation in sorted(annotations.items()):
        item = items.get(item_id)
        analysis = item.processing.analysis if item and item.processing else None
        if item is None or analysis is None:
            report.missing.append(item_id)
            continue
        reliability = item.processing.reliability or assess_item(item, policy)
        report.compared.append(
            ItemComparison(
                item_id=item_id,
                title=annotation.title or item.title,
                human=annotation,
                ai_score=analysis.score,
                ai_selected=selection_rule(item),
                ai_importance=importance_from_score(analysis.score),
                ai_categories=list(analysis.categories),
                ai_claim=analysis.claim.status if analysis.claim else None,
                ai_label=reliability.label,
                human_label=_label_with_claim(item, annotation.claim_status, policy),
            )
        )
    return report
