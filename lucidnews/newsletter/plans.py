"""Free/Premium plan limits.

No billing or paywall exists yet: both plans are deliberately unlimited until the
product is validated. Limits are applied in one place so gating can be turned on
later by editing ``PLAN_LIMITS`` instead of touching delivery code.
"""

from dataclasses import dataclass
from typing import Optional

from .models import DigestPreferences, Frequency, Plan, Subscriber


@dataclass(frozen=True)
class PlanLimits:
    max_categories: Optional[int] = None
    max_sources: Optional[int] = None
    max_items: Optional[int] = None
    frequencies: frozenset[Frequency] = frozenset(Frequency)


PLAN_LIMITS: dict[Plan, PlanLimits] = {
    Plan.FREE: PlanLimits(),
    Plan.PREMIUM: PlanLimits(),
}


def effective_preferences(subscriber: Subscriber) -> DigestPreferences:
    """Subscriber preferences clamped to what their plan allows."""
    limits = PLAN_LIMITS[subscriber.plan]
    prefs = subscriber.preferences
    updates: dict[str, object] = {}
    if limits.max_categories is not None and len(prefs.categories) > limits.max_categories:
        updates["categories"] = prefs.categories[: limits.max_categories]
    if limits.max_sources is not None and len(prefs.sources) > limits.max_sources:
        updates["sources"] = prefs.sources[: limits.max_sources]
    if limits.max_items is not None and (prefs.max_items is None or prefs.max_items > limits.max_items):
        updates["max_items"] = limits.max_items
    if prefs.frequency not in limits.frequencies:
        updates["frequency"] = Frequency.DAILY
    return prefs.model_copy(update=updates) if updates else prefs
