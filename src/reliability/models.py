"""Reliability data types.

Kept free of imports from ``src.models`` so the core models can embed them.
"""

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class SourceTier(str, Enum):
    """How much the publisher of an item's primary URL can be trusted."""

    OFFICIAL = "official"  # vendor/project's own site, docs, releases, standards bodies
    REPUTABLE = "reputable"  # established technical press and recognized experts
    COMMUNITY = "community"  # forums, aggregators, social platforms, open blogging hosts
    UNKNOWN = "unknown"  # not in the registry


class ClaimStatus(str, Enum):
    """AI judgement of how well the item's main claim is supported."""

    CONFIRMED = "confirmed"  # announced or documented by the primary party, or shipped
    REPORTED = "reported"  # reported by a credible outlet, not by the primary party
    UNVERIFIED = "unverified"  # single weak source or unclear evidence
    RUMOR = "rumor"  # leak, speculation, anonymous sourcing, prediction


class ReliabilityLabel(str, Enum):
    """Final reader-facing reliability label."""

    CONFIRMED = "confirmed"
    RELIABLE = "reliable"
    UNVERIFIED = "unverified"
    RUMOR = "rumor"


UNCONFIRMED_LABELS = frozenset({ReliabilityLabel.UNVERIFIED, ReliabilityLabel.RUMOR})


class ClaimAssessment(BaseModel):
    """Claim verification produced by the analysis stage."""

    status: ClaimStatus
    evidence: str = ""


class ReliabilityAssessment(BaseModel):
    """Deterministic combination of source trust and claim verification."""

    label: ReliabilityLabel
    source_tier: SourceTier
    source_domain: str = ""
    claim_status: Optional[ClaimStatus] = None
    reasons: List[str] = Field(default_factory=list)

    @property
    def is_confirmed_fact(self) -> bool:
        return self.label not in UNCONFIRMED_LABELS
