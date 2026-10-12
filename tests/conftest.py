from __future__ import annotations

import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture(autouse=True)
def _fresh_ai_budget():
    """Each test starts with the AI available (the run budget is process-wide)."""
    from lucidnews.ai import budget

    budget.start_run(None)
    yield
    budget.start_run(None)
