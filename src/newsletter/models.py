"""Subscriber and digest preference models."""

from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..i18n import DEFAULT_LANGUAGE
from ..taxonomy import Importance, normalize_categories


class Frequency(str, Enum):
    DAILY = "daily"
    WEEKLY = "weekly"  # stored now; delivery is on the roadmap (needs a multi-day item archive)


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

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        value = value.strip()
        local, _, domain = value.rpartition("@")
        if not local or "." not in domain or any(char.isspace() for char in value):
            raise ValueError(f"invalid email address: {value!r}")
        return value
