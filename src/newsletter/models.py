"""Subscriber and digest preference models."""

import hashlib
from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..i18n import DEFAULT_LANGUAGE
from ..taxonomy import Importance, normalize_categories


class Frequency(str, Enum):
    DAILY = "daily"
    WEEKLY = "weekly"  # the best items of the last seven days, sent on ``email.weekly_day``


class DetailLevel(str, Enum):
    BRIEF = "brief"  # title, reliability, summary, source
    COMPLETE = "complete"  # brief + the context blocks, references and tags of the enrichment


class SubscriptionStatus(str, Enum):
    PENDING = "pending"  # added, confirmation link not opened yet: receives nothing
    CONFIRMED = "confirmed"
    UNSUBSCRIBED = "unsubscribed"  # kept as a suppression entry so it is never mailed again


def subscriber_id(email: str) -> str:
    """Opaque id derived from the address, so addresses never appear in URLs."""
    return hashlib.sha256(email.strip().lower().encode("utf-8")).hexdigest()[:16]


class Plan(str, Enum):
    FREE = "free"
    PREMIUM = "premium"


class DigestPreferences(BaseModel):
    """What a subscriber wants to receive. Empty filters mean "everything"."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    language: str = DEFAULT_LANGUAGE
    categories: tuple[str, ...] = ()
    sources: tuple[str, ...] = ()  # source types ("hackernews") or feed names ("LWN.net")
    frequency: Frequency = Frequency.DAILY
    min_importance: Optional[Importance] = None
    include_unconfirmed: bool = True
    max_items: Optional[int] = Field(default=None, gt=0)
    detail_level: DetailLevel = DetailLevel.COMPLETE

    @field_validator("language")
    @classmethod
    def lowercase_language(cls, value: str) -> str:
        return value.strip().lower() or DEFAULT_LANGUAGE

    @field_validator("categories", mode="before")
    @classmethod
    def known_categories(cls, value: object) -> tuple[str, ...]:
        if not value:
            return ()
        if isinstance(value, str):
            value = [value]
        if not isinstance(value, (list, tuple)):
            raise ValueError("categories must be a list")
        unknown = [entry for entry in value if not normalize_categories([entry])]
        if unknown:
            raise ValueError(f"unknown categories: {unknown}")
        # Preferences may follow every category, so no per-item cap here.
        result: List[str] = []
        for entry in value:
            category = normalize_categories([entry])[0]
            if category not in result:
                result.append(category)
        return tuple(result)

    @field_validator("sources", mode="before")
    @classmethod
    def clean_sources(cls, value: object) -> tuple[str, ...]:
        if not value:
            return ()
        if isinstance(value, str):
            value = [value]
        return tuple(dict.fromkeys(str(entry).strip() for entry in value if str(entry).strip()))


class Subscriber(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str
    plan: Plan = Plan.FREE
    preferences: DigestPreferences = Field(default_factory=DigestPreferences)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    # Confirmed by default so subscribers.json files written before double opt-in keep
    # receiving; every way of adding a reader (web app, e-mail) creates a pending one.
    status: SubscriptionStatus = SubscriptionStatus.CONFIRMED
    confirmed_at: Optional[datetime] = None
    unsubscribed_at: Optional[datetime] = None

    @property
    def id(self) -> str:
        return subscriber_id(self.email)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        value = value.strip()
        local, _, domain = value.rpartition("@")
        if not local or "." not in domain or any(char.isspace() for char in value):
            raise ValueError(f"invalid email address: {value!r}")
        return value
