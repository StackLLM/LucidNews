"""Preview a subscriber's newsletter from the archive, through the code that sends it.

The preview plans the delivery with ``plan_deliveries`` and renders it with
``render_selection``, exactly like the pipeline. Only the source of the items differs:
the latest published edition (daily) or the last seven days (weekly), read from the
archive instead of the run in progress.
"""

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, List

from ..ai.summarizer import DailySummarizer
from ..archive import ItemArchive
from ..models import Config, ContentItem
from .build import render_selection
from .digest import plan_deliveries
from .models import Frequency, Subscriber, SubscriptionStatus
from .plans import effective_preferences
from .provider import secret
from .render import UNSUBSCRIBE_PLACEHOLDER
from . import tokens
from .weekly import window


def _skipped(item: ContentItem) -> bool:
    return bool(item.processing and item.processing.ai_skipped)


def _score(item: ContentItem) -> float:
    analysis = item.processing.analysis if item.processing else None
    return analysis.score if analysis and analysis.score is not None else -1.0


class PreviewService:
    def __init__(self, archive: ItemArchive, config: Config, profile_names: Dict[str, Dict[str, str]]):
        self.archive = archive
        self.config = config
        self.profile_names = profile_names

    def _daily_items(self) -> tuple[List[ContentItem], List[ContentItem], str, int, Dict[str, Any]] | None:
        run = self.archive.latest_published_run()
        if run is None:
            return None
        by_id = self.archive.get_items(self.archive.run_item_ids(run.id, selected_only=True))
        items = list(by_id.values())
        analyzed = sorted((i for i in items if not _skipped(i)), key=_score, reverse=True)
        unanalyzed = [i for i in items if _skipped(i)]
        day = run.started_at[:10]
        return analyzed, unanalyzed, day, run.fetched_count or len(items), {"edition": run.id}

    def preview(self, subscriber: Subscriber) -> Dict[str, Any]:
        email = self.config.email
        prefs = effective_preferences(subscriber)
        weekly = prefs.frequency is Frequency.WEEKLY
        cap = None
        unanalyzed: List[ContentItem] = []
        week_start = None
        meta: Dict[str, Any] = {}
        if weekly:
            today = datetime.now(timezone.utc).date()
            since, until, week_start = window(today)
            analyzed = [
                i for i in self.archive.items_between(since, until, selected_only=True) if not _skipped(i)
            ]
            day, total, cap = today.isoformat(), len(analyzed), (email.weekly_max_items if email else 15)
            meta = {"since": week_start, "until": day}
        else:
            daily = self._daily_items()
            if daily is None:
                return self._payload(prefs, None, weekly, meta, "no_edition")
            analyzed, unanalyzed, day, total, meta = daily

        links = bool(email and email.public_base_url and len(secret(email.signing_key_env) or "") >= tokens.MIN_KEY_LENGTH)
        plan = plan_deliveries(
            [subscriber.model_copy(update={"status": SubscriptionStatus.CONFIRMED})],
            analyzed,
            self.config.ai.languages or ["en"],
            frequency=prefs.frequency,
            unanalyzed=unanalyzed,
            max_items_cap=cap,
        )
        delivery = plan.deliveries[0]
        summarizer = DailySummarizer(
            profile_names=self.profile_names, profile_order=self.config.digest.profile_order
        )
        newsletter = asyncio.run(
            render_selection(
                delivery.preferences,
                delivery.items,
                delivery.unanalyzed,
                summarizer=summarizer,
                day=day,
                total_fetched=total,
                sender_name=email.sender_name if email else "LucidNews",
                unsubscribe_keyword=email.unsubscribe_keyword if email else "UNSUBSCRIBE",
                week_start=week_start,
                unsubscribe_link=links,
            )
        )
        payload = self._payload(delivery.preferences, newsletter, weekly, meta, None)
        fallback = plan.language_fallbacks.get(subscriber.email)
        if fallback:
            payload["language_fallback"] = {"wanted": fallback[0], "used": fallback[1]}
        return payload

    def _payload(self, prefs, newsletter, weekly: bool, meta: Dict[str, Any], reason) -> Dict[str, Any]:
        email = self.config.email
        return {
            "frequency": prefs.frequency.value,
            "detail_level": prefs.detail_level.value,
            "language": prefs.language,
            "weekly_day": email.weekly_day if email else 0,
            "reason": reason,  # "no_edition" when there is nothing to preview
            "subject": newsletter.subject if newsletter else None,
            # Each reader's own signed link replaces the placeholder when the e-mail is sent.
            "html": newsletter.email.html.replace(UNSUBSCRIBE_PLACEHOLDER, "#") if newsletter else None,
            "text": newsletter.email.text.replace(UNSUBSCRIBE_PLACEHOLDER, "(unsubscribe link)") if newsletter else None,
            "item_count": newsletter.item_count if newsletter else 0,
            "unanalyzed_count": newsletter.unanalyzed_count if newsletter else 0,
            "empty": newsletter.empty if newsletter else True,
            # The pipeline sends no weekly e-mail when nothing matches the week.
            "would_send": bool(newsletter) and not (weekly and newsletter.empty),
            **meta,
        }
