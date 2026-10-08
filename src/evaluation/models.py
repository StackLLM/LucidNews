"""What a human says about one item: the reference the AI is measured against."""

from datetime import datetime, timezone
from typing import List

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..reliability import ClaimStatus
from ..taxonomy import Importance, normalize_categories


class Annotation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item_id: str = Field(min_length=1, max_length=300)
    # Snapshot so the file stays readable without the archive.
    title: str = ""
    url: str = ""
    # Should this item be in the edition?
    relevant: bool
    importance: Importance
    categories: List[str] = Field(default_factory=list)
    claim_status: ClaimStatus
    notes: str = Field(default="", max_length=2000)
    annotated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("categories", mode="before")
    @classmethod
    def known_categories(cls, value: object) -> List[str]:
        if not value:
            return []
        if not isinstance(value, list):
            raise ValueError("categories must be a list")
        unknown = [entry for entry in value if not normalize_categories([entry])]
        if unknown:
            raise ValueError(f"unknown categories: {unknown}")
        return normalize_categories(value)  # same three-category cap as the AI
