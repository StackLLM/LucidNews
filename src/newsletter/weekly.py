"""Weekly digest: which days to send, and a record so a week is sent only once."""

import json
import logging
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from .._file_utils import _atomic_write_text

logger = logging.getLogger(__name__)

WINDOW_DAYS = 7


def iso_week(day: date) -> str:
    year, week, _ = day.isocalendar()
    return f"{year}-W{week:02d}"


def window(today: date) -> tuple[datetime, datetime, str]:
    """[since, until) covering the 7 days ending with ``today``, and the first day as text."""
    until = datetime(today.year, today.month, today.day, tzinfo=timezone.utc) + timedelta(days=1)
    since = until - timedelta(days=WINDOW_DAYS)
    return since, until, since.date().isoformat()


class WeeklyState:
    """``data/weekly_sent.json``: the ISO week of the last weekly digest sent."""

    def __init__(self, path: Path):
        self.path = Path(path)

    def last_week(self) -> Optional[str]:
        try:
            return json.loads(self.path.read_text(encoding="utf-8")).get("week")
        except (OSError, ValueError, AttributeError):
            return None

    def is_due(self, today: date, weekly_day: int) -> bool:
        return today.weekday() == weekly_day and self.last_week() != iso_week(today)

    def mark_sent(self, today: date) -> None:
        try:
            _atomic_write_text(self.path, json.dumps({"week": iso_week(today)}) + "\n")
        except OSError as exc:
            logger.warning("Could not record the weekly send: %s", exc)
