"""Delivery: daily and weekly newsletters, and the digest text they are built from."""

from datetime import datetime, timezone
from typing import List, Optional
import logging

from ..models import ContentItem
from ..ai.summarizer import DailySummarizer
from ..newsletter import DeliveryPlan, Frequency, plan_deliveries
from ..newsletter.build import render_selection
from ..newsletter.mailer import SendSummary
from ..newsletter.weekly import WeeklyState, window as weekly_window


logger = logging.getLogger(__name__)


class DeliveryMixin:
    """Delivery: daily and weekly newsletters, and the digest text they are built from."""

    async def send_newsletters(
        self,
        items: List[ContentItem],
        date: str,
        total_fetched: int,
        unanalyzed: Optional[List[ContentItem]] = None,
    ) -> DeliveryPlan:
        """Render and email one digest per distinct subscriber preference set."""
        plan = plan_deliveries(
            self.storage.subscribers.load(),
            items,
            self.config.ai.languages,
            unanalyzed=unanalyzed or (),
        )
        await self._deliver(plan, date, total_fetched)
        return plan

    async def send_weekly_newsletters(self, today: Optional[datetime] = None) -> Optional[DeliveryPlan]:
        """Send the week's best archived items to weekly subscribers, once per ISO week.

        Due on ``email.weekly_day`` (first run of that day). Without an archive or items
        nothing is sent and the week stays due.
        """
        email = self.config.email
        if getattr(self, "mailer", None) is None or not (email and email.enabled):
            return None
        day = (today or datetime.now(timezone.utc)).date()
        state = WeeklyState(self.storage.data_dir / "weekly_sent.json")
        if not state.is_due(day, email.weekly_day) or getattr(self, "archive", None) is None:
            return None
        since, until, week_start = weekly_window(day)
        try:
            items = self.archive.items_between(since, until, selected_only=True)
        except Exception as exc:
            logger.warning("Weekly digest skipped, archive unreadable: %s", exc)
            return None
        plan = plan_deliveries(
            self.storage.subscribers.load(),
            [item for item in items if not (item.processing and item.processing.ai_skipped)],
            self.config.ai.languages,
            frequency=Frequency.WEEKLY,
            max_items_cap=email.weekly_max_items,
        )
        totals = await self._deliver(plan, day.isoformat(), len(items), week_start=week_start)
        # A week where every send failed stays due: the next run of the day tries again.
        if totals.sent > 0 or totals.failed == 0:
            state.mark_sent(day)
        return plan

    async def _deliver(
        self, plan: DeliveryPlan, day: str, total_fetched: int, week_start: Optional[str] = None
    ) -> SendSummary:
        """Render each delivery of ``plan`` (the code path of the web preview) and send it."""
        email = self.config.email
        totals = SendSummary()
        if plan.not_confirmed:
            self.console.print(
                f"{self.icons['email']} {len(plan.not_confirmed)} subscriber(s) not confirmed or unsubscribed: nothing sent."
            )
        if plan.skipped_weekly and week_start is None:
            self.console.print(
                f"{self.icons['email']} {len(plan.skipped_weekly)} weekly subscriber(s) "
                f"receive their digest on day {email.weekly_day} of the week (0 = Monday)."
            )
        for email_addr, (wanted, used) in plan.language_fallbacks.items():
            self.console.print(
                f"[yellow]{self.icons['warning']} No '{wanted}' content this run; "
                f"sending '{used}' to {email_addr}.[/yellow]"
            )

        summarizer = DailySummarizer(
            profile_names=self.profiles.names,
            profile_order=self.config.digest.profile_order,
        )
        for delivery in plan.deliveries:
            language = delivery.preferences.language
            if week_start is not None and not delivery.items:
                continue  # nothing this week for these preferences: no empty e-mail
            newsletter = await render_selection(
                delivery.preferences,
                delivery.items,
                delivery.unanalyzed,
                summarizer=summarizer,
                day=day,
                total_fetched=total_fetched,
                sender_name=email.sender_name,
                unsubscribe_keyword=email.unsubscribe_keyword,
                week_start=week_start,
                unsubscribe_link=self.mailer.links_enabled,
            )
            self.console.print(
                f"{self.icons['email']} Sending {language.upper()} "
                f"{'weekly' if week_start else 'daily'} digest "
                f"({newsletter.item_count + newsletter.unanalyzed_count} items) "
                f"to {len(delivery.recipients)} subscriber(s)..."
            )
            summary = self.mailer.send_digest(
                newsletter,
                delivery.recipients,
                "weekly" if week_start else "daily",
                week_start or getattr(self, "run_id", None) or day,
            )
            totals.sent += summary.sent
            totals.failed += summary.failed
            self.console.print(
                f"   {self.icons['detail']} {summary.sent} sent, {summary.failed} failed"
                + (f", {summary.skipped} skipped (not confirmed)" if summary.skipped else "")
            )
        return totals

    async def _generate_summary(
        self,
        items: List[ContentItem],
        date: str,
        total_fetched: int,
        language: str = "en",
    ) -> str:
        """Generate daily summary.

        Args:
            items: Important items to include (already enriched with background/related)
            date: Date string
            total_fetched: Total items fetched
            language: Output language ("en" or "zh")

        Returns:
            str: Markdown summary
        """
        self.console.print(f"{self.icons['summary']} Generating daily summary...")

        summarizer = DailySummarizer(
            profile_names=self.profiles.names,
            profile_order=self.config.digest.profile_order,
        )

        return await summarizer.generate_summary(items, date, total_fetched, language=language)
