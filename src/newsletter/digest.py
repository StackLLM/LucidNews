"""Plan newsletter deliveries: one rendered digest per distinct preference set."""

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from ..models import ContentItem
from .models import DigestPreferences, Frequency, Subscriber
from .plans import effective_preferences
from .selection import select_items, select_unanalyzed


@dataclass
class Delivery:
    preferences: DigestPreferences  # language already resolved to an available one
    items: List[ContentItem]
    recipients: List[str] = field(default_factory=list)
    # Items the AI could not analyze (quota exhausted), shown in their own section.
    unanalyzed: List[ContentItem] = field(default_factory=list)


@dataclass
class DeliveryPlan:
    deliveries: List[Delivery] = field(default_factory=list)
    skipped_weekly: List[str] = field(default_factory=list)
    language_fallbacks: Dict[str, Tuple[str, str]] = field(default_factory=dict)


def plan_deliveries(
    subscribers: Iterable[Subscriber],
    items: Sequence[ContentItem],
    available_languages: Sequence[str],
    *,
    frequency: Frequency = Frequency.DAILY,
    unanalyzed: Sequence[ContentItem] = (),
    max_items_cap: Optional[int] = None,
) -> DeliveryPlan:
    """Group subscribers by effective preferences and select their items.

    ``available_languages`` are the languages AI content was generated in for this
    run; a subscriber asking for another language receives the first available one
    (recorded in ``language_fallbacks``) rather than a half-translated digest.
    ``max_items_cap`` bounds every subscriber's ``max_items`` (weekly digests).
    """
    if not available_languages:
        raise ValueError("at least one available language is required")
    available = [language.lower() for language in available_languages]
    plan = DeliveryPlan()
    groups: Dict[DigestPreferences, Delivery] = {}

    for subscriber in subscribers:
        prefs = effective_preferences(subscriber)
        if max_items_cap is not None and (prefs.max_items is None or prefs.max_items > max_items_cap):
            prefs = prefs.model_copy(update={"max_items": max_items_cap})
        if prefs.frequency is not frequency:
            plan.skipped_weekly.append(subscriber.email)
            continue
        if prefs.language not in available:
            plan.language_fallbacks[subscriber.email] = (prefs.language, available[0])
            prefs = prefs.model_copy(update={"language": available[0]})

        delivery = groups.get(prefs)
        if delivery is None:
            selected = select_items(items, prefs)
            delivery = Delivery(
                preferences=prefs,
                items=selected,
                unanalyzed=select_unanalyzed(unanalyzed, prefs, already=len(selected)),
            )
            groups[prefs] = delivery
        delivery.recipients.append(subscriber.email)

    plan.deliveries = list(groups.values())
    return plan
