"""Render one newsletter: the code path shared by sending and previewing."""

from dataclasses import dataclass
from typing import List, Optional

from ..ai.summarizer import DailySummarizer
from ..i18n import messages
from ..models import ContentItem
from .models import DigestPreferences
from .render import RenderedEmail, render_email


@dataclass(frozen=True)
class Newsletter:
    subject: str
    email: RenderedEmail
    item_count: int  # analyzed items
    unanalyzed_count: int

    @property
    def empty(self) -> bool:
        return self.item_count == 0 and self.unanalyzed_count == 0


async def render_selection(
    prefs: DigestPreferences,
    selected: List[ContentItem],
    unanalyzed: List[ContentItem],
    *,
    summarizer: DailySummarizer,
    day: str,
    total_fetched: int,
    sender_name: str,
    unsubscribe_keyword: str,
    week_start: Optional[str] = None,
) -> Newsletter:
    """Render items already chosen for ``prefs``. ``week_start`` makes it a weekly digest."""
    weekly = week_start is not None
    period = f"{week_start} → {day}" if weekly else day
    summary = await summarizer.generate_summary(
        selected,
        period,
        total_fetched,
        language=prefs.language,
        unanalyzed=unanalyzed,
        detail=prefs.detail_level.value,
        weekly=weekly,
    )
    labels = messages(prefs.language)
    subject = labels["email_subject_weekly" if weekly else "email_subject"].format(
        date=week_start if weekly else day
    )
    return Newsletter(
        subject=subject,
        email=render_email(
            summary,
            language=prefs.language,
            sender_name=sender_name,
            unsubscribe_keyword=unsubscribe_keyword,
        ),
        item_count=len(selected),
        unanalyzed_count=len(unanalyzed),
    )
