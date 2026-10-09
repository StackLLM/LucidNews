"""Social accounts as publishers.

A post on a social platform is judged on its **account**, not on the platform:
``mastodon.social`` is a community platform, but ``@bagder@mastodon.social`` is the
author of curl speaking about curl. Accounts are identified as ``platform:handle``:

- ``x:openai`` (x.com and twitter.com)
- ``mastodon:bagder@mastodon.social`` (any fediverse host using ``/@user`` paths)
- ``bluesky:bsky.app``
- ``telegram:durov``
"""

from typing import Optional
from urllib.parse import urlsplit

PLATFORMS = {"x", "mastodon", "bluesky", "telegram"}
_PLATFORM_ALIASES = {"twitter": "x"}

_X_HOSTS = {"x.com", "twitter.com", "mobile.twitter.com", "mobile.x.com"}
# First path segments on x.com that are pages, not accounts.
_X_RESERVED = {"i", "home", "search", "explore", "hashtag", "intent", "share", "settings", "notifications"}


def _host(url: str) -> str:
    host = (urlsplit(url).hostname or "").lower()
    return host.removeprefix("www.")


def account_of(url: str) -> Optional[str]:
    """``platform:handle`` of the account that published ``url``, if it is a social post."""
    host = _host(url)
    parts = [part for part in urlsplit(url).path.split("/") if part]
    if not host or not parts:
        return None
    if host in _X_HOSTS:
        handle = parts[0].lstrip("@").lower()
        return None if handle in _X_RESERVED else f"x:{handle}"
    if host == "t.me":
        if parts[0] == "s":  # public web preview: t.me/s/<channel>
            parts = parts[1:]
        return f"telegram:{parts[0].lower()}" if parts else None
    if host == "bsky.app":
        return f"bluesky:{parts[1].lower()}" if parts[0] == "profile" and len(parts) > 1 else None
    if parts[0].startswith("@") and len(parts[0]) > 1:
        user = parts[0][1:].lower()
        return f"mastodon:{user}" if "@" in user else f"mastodon:{user}@{host}"
    return None


def normalize_account(value: str) -> str:
    """Canonical ``platform:handle`` from config input (``X:@OpenAI`` -> ``x:openai``)."""
    platform, sep, handle = value.strip().lower().partition(":")
    platform = _PLATFORM_ALIASES.get(platform, platform)
    handle = handle.strip().lstrip("@")
    if not sep or platform not in PLATFORMS or not handle:
        raise ValueError(
            f"invalid account {value!r}: expected 'platform:handle' with platform in {sorted(PLATFORMS)}"
        )
    if platform == "mastodon" and "@" not in handle:
        raise ValueError(f"invalid account {value!r}: mastodon accounts need their server (user@host)")
    return f"{platform}:{handle}"
