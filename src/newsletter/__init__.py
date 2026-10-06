"""Newsletter foundations: subscribers, preferences, plans, selection and delivery planning."""

from .digest import Delivery, DeliveryPlan, plan_deliveries
from .models import DigestPreferences, Frequency, Plan, Subscriber
from .plans import PLAN_LIMITS, PlanLimits, effective_preferences
from .selection import matches, select_items
from .store import SubscriberStore

__all__ = [
    "Delivery",
    "DeliveryPlan",
    "DigestPreferences",
    "Frequency",
    "PLAN_LIMITS",
    "Plan",
    "PlanLimits",
    "Subscriber",
    "SubscriberStore",
    "effective_preferences",
    "matches",
    "plan_deliveries",
    "select_items",
]
