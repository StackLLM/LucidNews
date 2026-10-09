"""AI availability for one run: the token budget and the provider's quota.

Once the AI is out of quota for the run — the provider says its daily quota or
balance is used up, or the run reached ``ai.max_tokens_per_run`` — every later AI
call fails immediately with ``QuotaExhausted``. Nothing waits or retries: the run
carries on without AI and publishes the remaining items as "not analyzed".

A per-minute rate limit is *not* an exhausted quota: it is transient and is still
retried by the stages.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from .tokens import get_usage_snapshot


class AILimit(str, Enum):
    """Why the AI stopped being called during a run."""

    PROVIDER_QUOTA = "provider_quota"  # daily quota, credits or balance used up
    TOKEN_BUDGET = "token_budget"  # ai.max_tokens_per_run reached


class QuotaExhausted(RuntimeError):
    """The AI cannot be called any more in this run."""

    def __init__(self, limit: AILimit, detail: str = ""):
        super().__init__(f"AI unavailable for the rest of the run ({limit.value}){': ' + detail if detail else ''}")
        self.limit = limit


# Errors meaning "no more requests until the quota resets or the account is topped
# up". Gemini reports the quota id (e.g. GenerateRequestsPerDayPerProjectPerModel-
# FreeTier); a per-minute quota has a PerMinute id and stays a transient error.
_EXHAUSTED_PATTERNS = re.compile(
    r"per ?day"  # Gemini daily request/token quotas
    r"|insufficient_quota"  # OpenAI and compatible APIs: plan or billing limit
    r"|insufficient balance"  # DeepSeek (HTTP 402)
    r"|credit balance is too low"  # Anthropic
    r"|billing_hard_limit_reached",
    re.IGNORECASE,
)


def is_quota_exhausted_error(exc: BaseException) -> bool:
    """True when a provider error means the quota is used up, not just rate limited."""
    return bool(_EXHAUSTED_PATTERNS.search(str(exc)))


@dataclass
class _RunBudget:
    max_tokens: Optional[int] = None
    baseline: int = 0
    limit: Optional[AILimit] = None
    detail: str = ""


_state = _RunBudget()


def start_run(max_tokens: Optional[int]) -> None:
    """Reset the AI availability at the start of a run."""
    global _state
    _state = _RunBudget(max_tokens=max_tokens, baseline=get_usage_snapshot().total_tokens)


def tokens_used() -> int:
    """Tokens used since the start of the current run."""
    return max(0, get_usage_snapshot().total_tokens - _state.baseline)


def exhausted() -> Optional[AILimit]:
    """Why the AI is no longer available in this run, or None while it still is."""
    return _state.limit


def exhausted_detail() -> str:
    return _state.detail


def mark_exhausted(limit: AILimit, detail: str = "") -> None:
    if _state.limit is None:
        _state.limit = limit
        _state.detail = detail[:300]


def ensure_available() -> None:
    """Raise ``QuotaExhausted`` if the AI must not be called any more in this run."""
    if _state.limit is None and _state.max_tokens is not None and tokens_used() >= _state.max_tokens:
        mark_exhausted(AILimit.TOKEN_BUDGET, f"{tokens_used()} of {_state.max_tokens} tokens used")
    if _state.limit is not None:
        raise QuotaExhausted(_state.limit, _state.detail)
