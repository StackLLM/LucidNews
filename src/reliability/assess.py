"""Combine publisher trust and claim verification into a reliability label.

The source tier is computed deterministically from the item's primary URL (the
page the news links to, not the channel it was discovered on: a Hacker News post
linking to a GitHub release is judged on the release). The claim status comes
from the AI analysis. The combination is rule-based and conservative: a weak
source can only reach "reliable" when the analysis found the claim confirmed,
and a rumor is always labelled as a rumor, whatever the source.
"""

import re
from dataclasses import dataclass, field
from typing import Mapping, Optional
from urllib.parse import urlsplit

from ..models import ContentItem
from .models import (
    ClaimStatus,
    ReliabilityAssessment,
    ReliabilityLabel,
    SourceTier,
)
from .registry import DEFAULT_DOMAIN_TIERS

_GITHUB_RELEASE_PATH = re.compile(r"^/[^/]+/[^/]+/releases(?:/|$)")


@dataclass(frozen=True)
class ReliabilityPolicy:
    """Domain registry plus project overrides."""

    domain_tiers: Mapping[str, SourceTier] = field(
        default_factory=lambda: dict(DEFAULT_DOMAIN_TIERS)
    )

    @classmethod
    def with_overrides(cls, overrides: Optional[Mapping[str, SourceTier]] = None) -> "ReliabilityPolicy":
        tiers = dict(DEFAULT_DOMAIN_TIERS)
        for domain, tier in (overrides or {}).items():
            tiers[normalize_domain(domain)] = SourceTier(tier)
        return cls(domain_tiers=tiers)

    def tier_for_domain(self, host: str) -> SourceTier:
        host = normalize_domain(host)
        best: Optional[str] = None
        for domain in self.domain_tiers:
            if host == domain or host.endswith("." + domain):
                if best is None or len(domain) > len(best):
                    best = domain
        return self.domain_tiers[best] if best is not None else SourceTier.UNKNOWN


def normalize_domain(value: str) -> str:
    value = value.strip().lower()
    if "//" in value:
        value = urlsplit(value).hostname or ""
    value = value.split("/")[0].split(":")[0]
    return value.removeprefix("www.").rstrip(".")


def source_tier_for(item: ContentItem, policy: ReliabilityPolicy) -> tuple[SourceTier, str, str]:
    """Return (tier, domain, reason) for an item's primary URL."""
    parsed = urlsplit(str(item.url))
    domain = normalize_domain(parsed.hostname or "")

    pinned = item.metadata.get("source_trust")
    if pinned:
        try:
            return SourceTier(pinned), domain, f"source pinned as {SourceTier(pinned).value}"
        except ValueError:
            pass

    if domain == "github.com" and _GITHUB_RELEASE_PATH.match(parsed.path):
        return SourceTier.OFFICIAL, domain, "release published in the project's own repository"

    tier = policy.tier_for_domain(domain)
    if tier is SourceTier.UNKNOWN:
        return tier, domain, f"{domain or 'unknown host'} is not in the trust registry"
    return tier, domain, f"{domain} is registered as {tier.value}"


def combine(tier: SourceTier, claim: Optional[ClaimStatus]) -> ReliabilityLabel:
    if claim is ClaimStatus.RUMOR:
        return ReliabilityLabel.RUMOR
    if claim is ClaimStatus.UNVERIFIED:
        return ReliabilityLabel.UNVERIFIED
    if tier is SourceTier.OFFICIAL:
        return ReliabilityLabel.CONFIRMED
    if tier is SourceTier.REPUTABLE:
        return ReliabilityLabel.RELIABLE
    # Community or unknown publisher: only an explicit confirmation lifts it.
    if claim is ClaimStatus.CONFIRMED:
        return ReliabilityLabel.RELIABLE
    return ReliabilityLabel.UNVERIFIED


def assess_item(item: ContentItem, policy: Optional[ReliabilityPolicy] = None) -> ReliabilityAssessment:
    policy = policy or ReliabilityPolicy()
    tier, domain, tier_reason = source_tier_for(item, policy)
    analysis = item.processing.analysis if item.processing else None
    claim = analysis.claim.status if analysis and analysis.claim else None

    reasons = [tier_reason]
    if claim is None:
        reasons.append("claim status not assessed")
    else:
        evidence = analysis.claim.evidence.strip() if analysis and analysis.claim else ""
        reasons.append(f"claim {claim.value}" + (f": {evidence}" if evidence else ""))

    return ReliabilityAssessment(
        label=combine(tier, claim),
        source_tier=tier,
        source_domain=domain,
        claim_status=claim,
        reasons=reasons,
    )
