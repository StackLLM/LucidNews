import asyncio
import time

from src.ai.client import RateLimitedClient, RequestRateLimiter, create_ai_client
from src.models import AIConfig


def test_limiter_spaces_requests_evenly() -> None:
    limiter = RequestRateLimiter(requests_per_minute=600)  # one every 0.1 s
    starts = []

    class Inner:
        config = None

        async def complete(self, **kwargs):  # type: ignore[no-untyped-def]
            starts.append(time.monotonic())
            return "ok"

    client = RateLimitedClient(Inner(), limiter)

    async def run() -> None:
        await asyncio.gather(*(client.complete(system="s", user="u") for _ in range(4)))

    asyncio.run(run())

    gaps = [b - a for a, b in zip(starts, starts[1:])]
    assert all(gap >= 0.09 for gap in gaps)


def test_factory_wraps_only_when_quota_configured(monkeypatch) -> None:
    monkeypatch.setenv("TEST_OPENAI_KEY", "test")
    base = {"provider": "openai", "model": "m", "api_key_env": "TEST_OPENAI_KEY"}

    plain = create_ai_client(AIConfig(**base))
    limited = create_ai_client(AIConfig(**base, max_requests_per_minute=5))
    again = create_ai_client(AIConfig(**base, max_requests_per_minute=5))

    assert not isinstance(plain, RateLimitedClient)
    assert isinstance(limited, RateLimitedClient)
    assert limited.config.max_requests_per_minute == 5
    assert limited.limiter is again.limiter
