from datetime import datetime, timezone

import pytest

from lucidnews.models import (
    ClassificationResult,
    ContentAnalysis,
    ContentItem,
    ProcessingResult,
    ReliabilityConfig,
    SourceType,
)
from lucidnews.reliability import ReliabilityLabel, SourceTier
from lucidnews.reliability.accounts import account_of, normalize_account
from lucidnews.reliability.assess import ReliabilityPolicy, assess_item, independent_corroboration


def make_item(url: str, claim: str = "reported", **metadata) -> ContentItem:
    return ContentItem(
        id="x:1",
        source_type=SourceType.RSS,
        title="t",
        url=url,
        published_at=datetime(2026, 10, 6, tzinfo=timezone.utc),
        metadata=metadata,
        processing=ProcessingResult(
            classification=ClassificationResult(profile="tech-news", method="ai_match"),
            analysis=ContentAnalysis.model_validate(
                {"score": 7, "reason": "r", "summary": "s", "claim": {"status": claim, "evidence": "e"}}
            ),
        ),
    )


@pytest.mark.parametrize(
    ("url", "account"),
    [
        ("https://mastodon.social/@bagder/117392573268225646", "mastodon:bagder@mastodon.social"),
        ("https://fosstodon.org/@someone@other.host/1", "mastodon:someone@other.host"),
        ("https://x.com/OpenAI/status/1", "x:openai"),
        ("https://www.twitter.com/MistralAI/status/2", "x:mistralai"),
        ("https://x.com/i/web/status/1", None),
        ("https://t.me/s/durov/123", "telegram:durov"),
        ("https://t.me/durov/5", "telegram:durov"),
        ("https://bsky.app/profile/bsky.app/post/abc", "bluesky:bsky.app"),
        ("https://lwn.net/Articles/1/", None),
        ("https://mastodon.social/", None),
    ],
)
def test_account_of_social_urls(url, account) -> None:
    assert account_of(url) == account


def test_normalize_account_and_config_validation() -> None:
    assert normalize_account(" Twitter:@OpenAI ") == "x:openai"
    assert normalize_account("mastodon:@User@Host.example") == "mastodon:user@host.example"
    for bad in ("openai", "myspace:tom", "x:", "mastodon:bagder"):
        with pytest.raises(ValueError):
            normalize_account(bad)
    config = ReliabilityConfig(accounts={"X:@AnthropicAI": "official"})
    assert config.accounts == {"x:anthropicai": SourceTier.OFFICIAL}


def test_registered_account_outranks_its_platform() -> None:
    # The curl case: the maintainer's own post was "community" because of mastodon.social.
    curl = assess_item(make_item("https://mastodon.social/@bagder/117392573268225646"))
    assert (curl.source_tier, curl.label) == (SourceTier.OFFICIAL, ReliabilityLabel.CONFIRMED)
    assert curl.reasons[0] == "account mastodon:bagder@mastodon.social is registered as official"

    stranger = assess_item(make_item("https://mastodon.social/@someone/1"))
    assert (stranger.source_tier, stranger.label) == (SourceTier.COMMUNITY, ReliabilityLabel.UNVERIFIED)

    # A rumor stays a rumor, whoever posts it.
    assert assess_item(make_item("https://t.me/durov/5", claim="rumor")).label is ReliabilityLabel.RUMOR


def test_config_accounts_extend_the_registry() -> None:
    policy = ReliabilityPolicy.with_overrides(accounts={"x:openai": "official"})
    assert assess_item(make_item("https://x.com/OpenAI/status/1"), policy).label is ReliabilityLabel.CONFIRMED
    assert assess_item(make_item("https://x.com/OpenAI/status/1")).source_tier is SourceTier.COMMUNITY


def test_accounts_on_one_platform_are_independent_publishers() -> None:
    policy = ReliabilityPolicy.with_overrides(accounts={"x:openai": "official", "x:lwnnet": "reputable"})
    item = make_item(
        "https://x.com/someone/status/1",
        corroborating_urls=[
            "https://x.com/OpenAI/status/2",
            "https://x.com/LWNnet/status/3",
            "https://x.com/OpenAI/status/4",  # same account again
            "https://x.com/random/status/5",  # unregistered account
        ],
    )
    assert independent_corroboration(item, policy) == [
        ("x:openai", SourceTier.OFFICIAL),
        ("x:lwnnet", SourceTier.REPUTABLE),
    ]


@pytest.mark.parametrize(
    ("url", "tier"),
    [
        ("https://www.cnil.fr/fr/actualites", SourceTier.OFFICIAL),
        ("https://www.numerique.gouv.fr/actualites/x", SourceTier.OFFICIAL),
        ("https://cyber.gouv.fr/actualites/x", SourceTier.OFFICIAL),
        ("https://www.enisa.europa.eu/news/x", SourceTier.OFFICIAL),
        ("https://www.bsi.bund.de/x", SourceTier.OFFICIAL),
        ("https://www.lemagit.fr/actualites/x", SourceTier.REPUTABLE),
        ("https://www.journaldunet.com/x", SourceTier.REPUTABLE),
        ("https://www.heise.de/news/x", SourceTier.REPUTABLE),
        ("https://www.inria.fr/fr/x", SourceTier.REPUTABLE),
        ("https://linuxfr.org/news/x", SourceTier.COMMUNITY),
    ],
)
def test_french_and_european_publishers(url, tier) -> None:
    assert assess_item(make_item(url)).source_tier is tier
