from datetime import datetime, timezone

import pytest

from src.models import (
    ClassificationResult,
    ContentAnalysis,
    ContentItem,
    ProcessingResult,
    ReliabilityConfig,
    RSSSourceConfig,
    SourceType,
)
from src.reliability import ClaimStatus, ReliabilityLabel, SourceTier
from src.reliability.assess import ReliabilityPolicy, assess_item, combine, normalize_domain


def make_item(url: str, claim: dict | None = None, **metadata) -> ContentItem:
    return ContentItem(
        id="x:1",
        source_type=SourceType.HACKERNEWS,
        title="t",
        url=url,
        published_at=datetime(2026, 10, 5, tzinfo=timezone.utc),
        metadata=metadata,
        processing=ProcessingResult(
            classification=ClassificationResult(profile="tech-news", method="ai_match"),
            analysis=ContentAnalysis.model_validate(
                {"score": 8, "reason": "r", "summary": "s", "claim": claim}
            ),
        ),
    )


@pytest.mark.parametrize(
    ("url", "tier"),
    [
        ("https://openai.com/index/new-model", SourceTier.OFFICIAL),
        ("https://platform.openai.com/docs", SourceTier.OFFICIAL),
        ("https://developers.cloudflare.com/changelog/post/x", SourceTier.OFFICIAL),
        ("https://www.huawei.com/en/news/2026/10/x", SourceTier.OFFICIAL),
        ("https://github.com/rui314/mold/releases/tag/v3.0.0", SourceTier.OFFICIAL),
        ("https://github.com/someone/project", SourceTier.COMMUNITY),
        ("https://lilianweng.github.io/posts/x", SourceTier.REPUTABLE),
        ("https://random.github.io/blog", SourceTier.COMMUNITY),
        ("https://lwn.net/Articles/1/", SourceTier.REPUTABLE),
        ("https://news.ycombinator.com/item?id=1", SourceTier.COMMUNITY),
        ("https://unknown-blog.example/post", SourceTier.UNKNOWN),
    ],
)
def test_source_tier_from_primary_url(url, tier) -> None:
    assert assess_item(make_item(url)).source_tier is tier


@pytest.mark.parametrize(
    ("tier", "claim", "label"),
    [
        (SourceTier.OFFICIAL, None, ReliabilityLabel.CONFIRMED),
        (SourceTier.OFFICIAL, ClaimStatus.CONFIRMED, ReliabilityLabel.CONFIRMED),
        (SourceTier.OFFICIAL, ClaimStatus.RUMOR, ReliabilityLabel.RUMOR),
        (SourceTier.REPUTABLE, ClaimStatus.REPORTED, ReliabilityLabel.RELIABLE),
        (SourceTier.REPUTABLE, ClaimStatus.UNVERIFIED, ReliabilityLabel.UNVERIFIED),
        (SourceTier.COMMUNITY, None, ReliabilityLabel.UNVERIFIED),
        (SourceTier.COMMUNITY, ClaimStatus.REPORTED, ReliabilityLabel.UNVERIFIED),
        (SourceTier.COMMUNITY, ClaimStatus.CONFIRMED, ReliabilityLabel.RELIABLE),
        (SourceTier.UNKNOWN, ClaimStatus.RUMOR, ReliabilityLabel.RUMOR),
    ],
)
def test_combination_rules_are_conservative(tier, claim, label) -> None:
    assert combine(tier, claim) is label


def test_rumor_on_official_domain_is_still_a_rumor() -> None:
    item = make_item(
        "https://openai.com/blog/x", {"status": "rumor", "evidence": "anonymous sources"}
    )
    result = assess_item(item)

    assert result.label is ReliabilityLabel.RUMOR
    assert not result.is_confirmed_fact
    assert "anonymous sources" in result.reasons[-1]


def test_config_override_and_pinned_feed_trust() -> None:
    policy = ReliabilityPolicy.with_overrides({"https://www.Internal-Blog.example/": "official"})
    assert assess_item(make_item("https://news.internal-blog.example/a"), policy).source_tier is SourceTier.OFFICIAL

    pinned = make_item("https://unknown.example/post", source_trust="reputable")
    assert assess_item(pinned).source_tier is SourceTier.REPUTABLE


def test_invalid_claim_degrades_to_not_assessed() -> None:
    item = make_item("https://lwn.net/a", {"status": "probably", "evidence": ""})

    assert item.processing.analysis.claim is None
    assert assess_item(item).label is ReliabilityLabel.RELIABLE


def test_rss_trust_and_reliability_config_validate() -> None:
    feed = RSSSourceConfig(name="Vendor", url="https://vendor.example/feed", trust="official")
    config = ReliabilityConfig(domains={"vendor.example": "official"}, exclude_labels=["rumor"])

    assert feed.trust is SourceTier.OFFICIAL
    assert config.exclude_labels == [ReliabilityLabel.RUMOR]


def test_normalize_domain() -> None:
    assert normalize_domain("https://WWW.Example.com:443/path") == "example.com"
    assert normalize_domain("example.com.") == "example.com"


from src.reliability.assess import independent_corroboration, site_of


def test_site_of_groups_subdomains_and_country_suffixes() -> None:
    assert site_of("blog.example.com") == "example.com"
    assert site_of("news.bbc.co.uk") == "bbc.co.uk"
    assert site_of("www.cert.ssi.gouv.fr") == "ssi.gouv.fr"


def test_only_distinct_trusted_sites_count_as_corroboration() -> None:
    item = make_item("https://news.ycombinator.com/item?id=1")
    item.metadata["corroborating_urls"] = [
        "https://arstechnica.com/a",
        "https://www.arstechnica.com/b",  # same site
        "https://reddit.com/r/x",  # community
        "https://unknown.example/c",  # unknown
        "https://lwn.net/d",
        "https://news.ycombinator.com/item?id=2",  # same site as primary
    ]

    assert independent_corroboration(item, ReliabilityPolicy()) == [
        ("arstechnica.com", SourceTier.REPUTABLE),
        ("lwn.net", SourceTier.REPUTABLE),
    ]


@pytest.mark.parametrize(
    ("primary", "claim", "corroborating", "label"),
    [
        # community + reported, one reputable outlet also reports it
        ("https://news.ycombinator.com/x", {"status": "reported"}, ["https://lwn.net/a"], ReliabilityLabel.RELIABLE),
        # weak claim needs two independent reputable outlets
        ("https://unknown.example/x", {"status": "unverified"}, ["https://lwn.net/a"], ReliabilityLabel.UNVERIFIED),
        ("https://unknown.example/x", {"status": "unverified"}, ["https://lwn.net/a", "https://theregister.com/b"], ReliabilityLabel.RELIABLE),
        # the party concerned published it too
        ("https://techcrunch.com/x", {"status": "reported"}, ["https://openai.com/index/y"], ReliabilityLabel.CONFIRMED),
        # a repeated rumor stays a rumor
        ("https://x.com/leaker", {"status": "rumor"}, ["https://lwn.net/a", "https://openai.com/b"], ReliabilityLabel.RUMOR),
        # community-only echoes do not help
        ("https://unknown.example/x", None, ["https://reddit.com/r/a", "https://medium.com/b"], ReliabilityLabel.UNVERIFIED),
    ],
)
def test_corroboration_rules(primary, claim, corroborating, label) -> None:
    item = make_item(primary, claim)
    item.metadata["corroborating_urls"] = corroborating

    result = assess_item(item)

    assert result.label is label
    if label is not ReliabilityLabel.RUMOR and result.corroborated_by:
        assert any("corroborated by" in reason for reason in result.reasons)
