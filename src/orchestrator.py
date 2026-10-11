"""Main orchestrator coordinating the entire workflow."""

import asyncio
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Literal, Optional, Sequence
from urllib.parse import unquote_plus, urlsplit
import httpx
import logging
from rich.console import Console

from .console_icons import get_icons
from .models import Config, ContentItem
from .storage.manager import StorageManager, safe_output_path
from .services.email import EmailManager
from .services.webhook import WebhookNotifier
from .scrapers.github import GitHubScraper
from .scrapers.hackernews import HackerNewsScraper
from .scrapers.rss import RSSScraper
from .scrapers.reddit import RedditScraper
from .scrapers.telegram import TelegramScraper
from .scrapers.twitter import TwitterScraper
from .scrapers.twitter_playwright import TwitterPlaywrightScraper
from .scrapers.ossinsight import OSSInsightScraper
from .scrapers.gdelt import GDELTScraper
from .scrapers.google_news import GoogleNewsScraper
from .ai import budget
from .ai.client import create_ai_client
from .ai.analyzer import ContentAnalyzer
from .ai.summarizer import DailySummarizer
from .ai.enricher import ContentEnricher, EnrichmentBatchResult
from .ai.tokens import get_usage_snapshot
from .processing import ProfileRegistry
from .processing.tools import ToolRegistry
from .reliability.assess import ReliabilityPolicy, assess_item, source_tier_for
from .reliability.models import SourceTier
from .i18n import messages
from .newsletter import DeliveryPlan, Frequency, plan_deliveries
from .newsletter.build import render_selection
from .newsletter.mailer import SendSummary, build_mailer
from .newsletter.weekly import WeeklyState, window as weekly_window
from .archive import ItemArchive, content_hash
from .source_health import (
    SCRAPER_SOURCE_TYPES,
    HealthStatus,
    assess_health,
    build_source_outcomes,
    configured_source_keys,
    source_key,
)
from .source_quality import compute_source_quality, item_source_key


logger = logging.getLogger(__name__)

# Identify the collector honestly; some feeds reject the default httpx agent.
COLLECTOR_USER_AGENT = "Mozilla/5.0 (compatible; LucidNews/1.0; RSS reader)"

_TRACKING_QUERY_PARAMETERS = {
    "_ga",
    "dclid",
    "fbclid",
    "gclid",
    "igshid",
    "li_fat_id",
    "mc_cid",
    "mc_eid",
    "msclkid",
    "ttclid",
    "twclid",
    "vero_id",
}


def _deduplication_url_key(url: str) -> tuple[str, str, str, str, Optional[int], str, str]:
    """Return a conservative URL identity key for cross-source deduplication."""
    parsed = urlsplit(url)
    scheme = parsed.scheme.lower()
    host = (parsed.hostname or "").lower()
    port = parsed.port
    if (scheme, port) in {("http", 80), ("https", 443)}:
        port = None

    path = parsed.path.rstrip("/") or "/"
    query_parts = []
    for part in parsed.query.split("&") if parsed.query else []:
        name = unquote_plus(part.partition("=")[0]).lower()
        if name.startswith("utm_") or name in _TRACKING_QUERY_PARAMETERS:
            continue
        query_parts.append(part)

    return (
        scheme,
        parsed.username or "",
        parsed.password or "",
        host,
        port,
        path,
        "&".join(query_parts),
    )


@dataclass
class BalancedDigestResult:
    """Items and selection statistics from balanced digest filtering."""

    items: List[ContentItem]
    enabled: bool = False
    group_counts: Dict[str, int] = field(default_factory=dict)
    group_limits: Dict[str, Optional[int]] = field(default_factory=dict)
    duplicate_categories: List[str] = field(default_factory=list)


@dataclass
class FilteringPipelineResult:
    """Items and statistics from score, topic, and digest filtering."""

    items: List[ContentItem]
    threshold_count: int
    topic_dedup_count: int
    topic_dedup_removed: int
    balanced_digest: BalancedDigestResult
    eligible_count: Optional[int] = None


@dataclass
class SourceFetchOutcome:
    """Result of fetching one configured source."""

    source_name: str
    status: Literal["success", "empty", "failure"]
    items: List[ContentItem] = field(default_factory=list)
    error: Optional[str] = None
    # Sub-sources (e.g. one RSS feed) that failed while the scraper as a whole succeeded.
    source_errors: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, object]:
        result: Dict[str, object] = {
            "source": self.source_name,
            "status": self.status,
            "item_count": len(self.items),
        }
        if self.error is not None:
            result["error"] = self.error
        if self.source_errors:
            result["source_errors"] = dict(self.source_errors)
        return result


@dataclass
class FetchReport:
    """Aggregate diagnostics for one fetch across configured sources."""

    outcomes: List[SourceFetchOutcome] = field(default_factory=list)

    @property
    def status(self) -> Literal["not_attempted", "success", "partial_failure", "failure"]:
        if not self.outcomes:
            return "not_attempted"
        if self.failed_count == len(self.outcomes):
            return "failure"
        if self.failed_count:
            return "partial_failure"
        return "success"

    @property
    def failed_count(self) -> int:
        return sum(outcome.status == "failure" for outcome in self.outcomes)

    @property
    def all_failed(self) -> bool:
        return bool(self.outcomes) and self.failed_count == len(self.outcomes)

    def failure_message(self) -> str:
        failures = "; ".join(
            f"{outcome.source_name}: {outcome.error or 'unknown error'}"
            for outcome in self.outcomes
            if outcome.status == "failure"
        )
        return f"All {len(self.outcomes)} attempted sources failed ({failures})"

    def to_dict(self) -> Dict[str, object]:
        return {
            "status": self.status,
            "attempted": len(self.outcomes),
            "successful": len(self.outcomes) - self.failed_count,
            "empty": sum(outcome.status == "empty" for outcome in self.outcomes),
            "failed": self.failed_count,
            "item_count": sum(len(outcome.items) for outcome in self.outcomes),
            "sources": [outcome.to_dict() for outcome in self.outcomes],
        }


class PipelineOrchestrator:
    """Orchestrates the complete workflow for content aggregation and analysis."""

    icons = get_icons()

    def __init__(
        self,
        config: Config,
        storage: StorageManager,
        console: Optional[Console] = None,
        profiles: Optional[ProfileRegistry] = None,
    ):
        """Initialize orchestrator.

        Args:
            config: Application configuration
            storage: Storage manager
            console: Shared Rich Console instance
        """
        self.config = config
        self.storage = storage
        self.console = console or Console(stderr=True)
        self.icons = get_icons(config.display.icon_style)
        self.profiles = profiles or ProfileRegistry.load(
            Path(config.processing.profiles_dir), config.processing.default_profile
        )
        self.profiles.validate_source_references(
            config.sources.model_dump(mode="json")
        )
        for profile_id in config.processing.profile_settings:
            self.profiles.get(profile_id)
        if config.digest.profile_order:
            configured_profiles = set(config.digest.profile_order)
            unknown_profiles = configured_profiles - self.profiles.ids
            if unknown_profiles:
                raise ValueError(
                    "digest.profile_order contains unknown profiles "
                    f"({', '.join(sorted(unknown_profiles))})"
                )
            config.digest.profile_order.extend(
                profile.id
                for profile in self.profiles.profiles
                if profile.id not in configured_profiles
            )
        self.reliability_policy = ReliabilityPolicy.with_overrides(
            config.reliability.domains, config.reliability.accounts
        )
        self.email_manager = EmailManager(config.email, console=self.console) if config.email else None
        self.mailer = (
            build_mailer(config.email, self.storage.subscribers, console=self.console)
            if config.email and config.email.enabled
            else None
        )
        self.webhook_notifier = (
            WebhookNotifier(config.webhook, console=self.console, icons=self.icons)
            if config.webhook and config.webhook.enabled
            else None
        )
        self.last_fetch_report: Optional[FetchReport] = None
        self.archive: Optional[ItemArchive] = None
        self.run_id: Optional[str] = None

    def _open_archive(self) -> Optional[ItemArchive]:
        settings = getattr(self.config, "archive", None)
        if settings is None or not settings.enabled:
            return None
        path = Path(settings.path)
        try:
            if not path.is_absolute():
                path = Path(self.storage.data_dir) / path
            return ItemArchive(path)
        except Exception as exc:  # the digest must not depend on the archive
            logger.warning("Archive disabled for this run (%s): %s", path, exc)
            self.console.print(f"[yellow]{self.icons['warning']} Archive unavailable: {exc}[/yellow]")
            return None

    def _archive(self, method: str, *args, **kwargs) -> None:
        """Best-effort archive write; failures are logged, never raised."""
        if getattr(self, "archive", None) is None:
            return
        if method != "start_run" and getattr(self, "run_id", None) is None:
            return
        try:
            if method == "start_run":
                self.run_id = self.archive.start_run(*args, **kwargs)
            else:
                getattr(self.archive, method)(self.run_id, *args, **kwargs)
        except Exception as exc:
            logger.warning("Archive %s failed: %s", method, exc)

    async def run(self, force_hours: int = None) -> None:
        """Execute the complete workflow.

        Args:
            force_hours: Optional override for time window in hours
        """
        self.console.print(
            f"[bold cyan]{self.icons['start']} LucidNews - Starting aggregation...[/bold cyan]\n"
        )

        # Check email subscriptions if configured
        if (
            self.email_manager
            and self.config.email
            and self.config.email.enabled
            and self.config.email.imap_enabled
        ):
            self.console.print(f"{self.icons['email']} Checking for new email subscriptions...")
            self.email_manager.check_subscriptions(self.storage, self.mailer)

        try:
            budget.start_run(getattr(getattr(self.config, "ai", None), "max_tokens_per_run", None))
            # 1. Determine time window
            since = self._determine_time_window(force_hours)
            self.archive = self._open_archive()
            self._archive("start_run", since)
            self.console.print(
                f"{self.icons['date']} Fetching content since: "
                f"{since.strftime('%Y-%m-%d %H:%M:%S')}\n"
            )

            # 2. Fetch content from all sources
            all_items = await self.fetch_all_sources(since)
            self._fetched_items = all_items
            self.console.print(
                f"{self.icons['fetched']} Fetched {len(all_items)} items from all sources\n"
            )

            if self.last_fetch_report and self.last_fetch_report.all_failed:
                raise RuntimeError(self.last_fetch_report.failure_message())

            if not all_items:
                self.console.print("[yellow]No new content found. Exiting.[/yellow]")
                self._archive("record_selection_stats", url_merged=0, topic_merged=0, above_threshold=0)
                self._finish_archive("empty", all_items, [])
                await self.send_weekly_newsletters()
                return

            # 3. Merge cross-source duplicates (same URL from different sources)
            merged_items = self.merge_cross_source_duplicates(all_items)
            url_merged = len(all_items) - len(merged_items)
            if len(merged_items) < len(all_items):
                self.console.print(
                    f"{self.icons['merge']} Merged "
                    f"{len(all_items) - len(merged_items)} cross-source duplicates "
                    f"→ {len(merged_items)} unique items\n"
                )

            merged_items = self._add_pending_retries(merged_items)

            # 4. Analyze with AI
            analyzed_items = await self.analyze_items(merged_items)
            self._archive("record_items", analyzed_items)
            self.console.print(
                f"{self.icons['ai']} Analyzed {len(analyzed_items)} items with AI\n"
            )

            # Archive signals for selection: source quality and earlier reports.
            self._load_archive_signals(analyzed_items)

            # 5. Filter, deduplicate, and balance the digest
            filtering_result = await self.select_digest_items(
                analyzed_items,
            )
            important_items = filtering_result.items
            # Counters for the quality overview (url merges, topic merges, items above threshold).
            self._archive(
                "record_selection_stats",
                url_merged=url_merged,
                topic_merged=filtering_result.topic_dedup_removed,
                above_threshold=filtering_result.threshold_count,
            )
            # Only when the AI ran out of quota: items it could not analyze.
            unanalyzed = self.select_unanalyzed_items(analyzed_items)

            # Show per-sub-source selection breakdown
            selected_counts: Dict[str, int] = defaultdict(int)
            for item in important_items:
                key = f"{item.source_type.value}/{self._sub_source_label(item)}"
                selected_counts[key] += 1
            for source_key, count in sorted(selected_counts.items()):
                self.console.print(f"      {self.icons['detail']} {source_key}: {count}")
            self.console.print("")

            # 6. Search related stories + enrich with background knowledge (2nd AI pass)
            await self.enrich_items(important_items)
            self._archive("record_items", important_items, selected=True)
            self._archive("record_items", unanalyzed, selected=True)

            # 7. Generate and save daily summaries for each configured language
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            for lang in self.config.ai.languages:
                summarizer = DailySummarizer(
                    profile_names=self.profiles.names,
                    profile_order=self.config.digest.profile_order,
                )
                summary = await summarizer.generate_summary(
                    important_items, today, len(all_items), language=lang, unanalyzed=unanalyzed
                )

                # Save to data/summaries/
                summary_path = self.storage.save_daily_summary(today, summary, language=lang)
                self.console.print(
                    f"{self.icons['save']} Saved {lang.upper()} summary to: {summary_path}\n"
                )

                # Send webhook notification if configured
                if self.webhook_notifier:
                    await self.webhook_notifier.send_daily_summary(
                        summary=summary,
                        important_items=important_items,
                        all_items_count=len(all_items),
                        date=today,
                        lang=lang,
                        summarizer=summarizer,
                    )

            if self.mailer is not None:
                await self.send_newsletters(
                    important_items, today, len(all_items), unanalyzed=unanalyzed
                )
                await self.send_weekly_newsletters()

            self._finish_archive("success", all_items, important_items + unanalyzed)

            self.console.print(
                f"[bold green]{self.icons['success']} "
                "LucidNews completed successfully![/bold green]"
            )
            usage = get_usage_snapshot()
            if usage.total_tokens > 0:
                max_tokens = getattr(self.config.ai, "max_tokens_per_run", None)
                self.console.print(
                    f"\n{self.icons['tokens']} Token usage this run: "
                    f"{usage.total_tokens} tokens "
                    f"(input: {usage.total_input_tokens}, output: {usage.total_output_tokens})"
                    + (f", budget {max_tokens}" if max_tokens else "")
                )
                for provider, u in sorted(usage.per_provider.items()):
                    if u.total <= 0:
                        continue
                    self.console.print(
                        f"   {self.icons['detail']} {provider}: {u.total} tokens "
                        f"(in: {u.input_tokens}, out: {u.output_tokens})"
                    )

        except Exception as e:
            self.console.print(
                f"[bold red]{self.icons['error']} Error: {e}[/bold red]"
            )
            self._finish_archive(
                "failed", getattr(self, "_fetched_items", []), [], error=str(e)
            )

            # Send webhook failure notification if configured
            if self.webhook_notifier:
                await self.webhook_notifier.send_failure(
                    date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                    error_message=str(e),
                )

            raise

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

    def _finish_archive(
        self,
        status: str,
        fetched_items: List[ContentItem],
        selected_items: List[ContentItem],
        error: Optional[str] = None,
    ) -> None:
        """Record per-source outcomes and the run result, then flag unhealthy sources."""
        if getattr(self, "archive", None) is None or getattr(self, "run_id", None) is None:
            return
        report = getattr(self, "last_fetch_report", None)
        source_errors: Dict[str, str] = {}
        failed_types: Dict[str, str] = {}
        for outcome in report.outcomes if report else []:
            source_errors.update(outcome.source_errors)
            if outcome.status == "failure":
                source_type = SCRAPER_SOURCE_TYPES.get(outcome.source_name, outcome.source_name)
                failed_types[source_type] = outcome.error or "unknown error"
        try:
            configured = configured_source_keys(self.config)
        except Exception:
            configured = {}
        outcomes = build_source_outcomes(
            configured, fetched_items, selected_items, source_errors, failed_types
        )
        self._archive("record_source_runs", outcomes)
        limit = budget.exhausted()
        self._archive(
            "finish_run",
            status,
            fetch_report=self._fetch_report_dict(),
            error=error,
            ai_limit=limit.value if limit else None,
            tokens_used=budget.tokens_used(),
        )
        if status != "failed":
            self._warn_unhealthy_sources()

    def _warn_unhealthy_sources(self, days: int = 14) -> None:
        try:
            rows = self.archive.source_run_rows(datetime.now(timezone.utc) - timedelta(days=days))
        except Exception as exc:
            logger.warning("Source health check failed: %s", exc)
            return
        try:
            configured = set(configured_source_keys(self.config))
        except Exception:
            configured = set()
        flagged = [
            health
            for health in assess_health(rows)
            if health.status in (HealthStatus.DEAD, HealthStatus.FAILING)
            and (not configured or health.source_key in configured)
        ]
        if not flagged:
            return
        self.console.print(
            f"\n[yellow]{self.icons['warning']} {len(flagged)} source(s) need attention "
            f"(last {days} days):[/yellow]"
        )
        for health in flagged:
            self.console.print(
                f"[yellow]   {self.icons['detail']} {health.source_key}: {health.status.value}, "
                f"{'; '.join(health.reasons)}[/yellow]"
            )
        self.console.print("[dim]   Run `uv run lucidnews-sources` for the full report.[/dim]")

    def _fetch_report_dict(self) -> Optional[Dict[str, object]]:
        report = getattr(self, "last_fetch_report", None)
        return report.to_dict() if report else None

    def _reuse_archived_analyses(self, items: List[ContentItem]) -> List[ContentItem]:
        """Restore stored analyses for unchanged items; return the items still to analyze."""
        archive = getattr(self, "archive", None)
        if archive is None or not self.config.archive.reuse_analysis:
            return items
        try:
            previous = archive.get_items([item.id for item in items])
        except Exception as exc:
            logger.warning("Archive lookup failed, analyzing everything: %s", exc)
            return items

        remaining = []
        for item in items:
            stored = previous.get(item.id)
            stored_analysis = stored.processing.analysis if stored and stored.processing else None
            if (
                stored_analysis is not None
                and stored_analysis.score is not None
                and content_hash(stored) == content_hash(item)
            ):
                item.processing = stored.processing.model_copy(deep=True)
                if not getattr(self.config.archive, "reuse_enrichment", True):
                    item.processing.artifacts.clear()
                item.processing.reliability = assess_item(item, self.reliability_policy)
            else:
                remaining.append(item)
        reused = len(items) - len(remaining)
        if reused:
            self.console.print(
                f"   {self.icons['detail']} Reused {reused} analyses from the archive"
            )
        return remaining

    def _add_pending_retries(self, items: List[ContentItem]) -> List[ContentItem]:
        """Append archived items whose analysis failed in a previous run."""
        archive = getattr(self, "archive", None)
        settings = getattr(self.config, "archive", None)
        if archive is None or settings is None or not settings.retry_failed_analysis:
            return items
        try:
            pending = archive.pending_items(
                first_seen_after=datetime.now(timezone.utc)
                - timedelta(hours=settings.retry_window_hours),
                max_attempts=settings.max_analysis_attempts,
                exclude_ids=[item.id for item in items],
            )
        except Exception as exc:
            logger.warning("Could not load pending retries from the archive: %s", exc)
            return items
        if pending:
            self.console.print(
                f"{self.icons['detail']} Retrying {len(pending)} item(s) whose analysis "
                "failed in a previous run\n"
            )
        return items + pending

    async def _pause_before_retry(self, count: int, stage: str) -> bool:
        delay = getattr(self.config.ai, "failed_retry_delay_sec", None)
        if delay is None or count == 0 or budget.exhausted() is not None:
            return False
        self.console.print(
            f"[yellow]{self.icons['warning']} {count} item(s) failed {stage}; "
            f"retrying once in {delay:g}s...[/yellow]"
        )
        await asyncio.sleep(delay)
        return True

    def _determine_time_window(self, force_hours: int = None) -> datetime:
        if force_hours:
            since = datetime.now(timezone.utc) - timedelta(hours=force_hours)
        else:
            hours = self.config.collection.time_window_hours
            since = datetime.now(timezone.utc) - timedelta(hours=hours)
        return since

    async def fetch_all_sources(self, since: datetime) -> List[ContentItem]:
        """Fetch content from all configured sources.

        This is a stable stage entry point for integrations such as MCP.

        Args:
            since: Fetch items published after this time

        Returns:
            List[ContentItem]: All fetched items
        """
        self.last_fetch_report = None
        async with httpx.AsyncClient(
            timeout=30.0, headers={"User-Agent": COLLECTOR_USER_AGENT}
        ) as client:
            tasks = []

            # GitHub sources
            if self.config.sources.github:
                github_scraper = GitHubScraper(self.config.sources.github, client)
                tasks.append(self._fetch_with_progress("GitHub", github_scraper, since))

            # Hacker News
            if self.config.sources.hackernews.enabled:
                hn_scraper = HackerNewsScraper(self.config.sources.hackernews, client)
                tasks.append(self._fetch_with_progress("Hacker News", hn_scraper, since))

            # RSS feeds
            if self.config.sources.rss:
                from .extractors import ExtractorRegistry
                rss_scraper = RSSScraper(
                    self.config.sources.rss,
                    client,
                    ExtractorRegistry(self.config.extractors),
                )
                tasks.append(self._fetch_with_progress("RSS Feeds", rss_scraper, since))

            # Reddit
            if self.config.sources.reddit.enabled:
                reddit_scraper = RedditScraper(self.config.sources.reddit, client)
                tasks.append(self._fetch_with_progress("Reddit", reddit_scraper, since))

            # Telegram
            if self.config.sources.telegram.enabled:
                telegram_scraper = TelegramScraper(self.config.sources.telegram, client)
                tasks.append(self._fetch_with_progress("Telegram", telegram_scraper, since))

            # Twitter (Apify or Playwright mode)
            if self.config.sources.twitter and self.config.sources.twitter.enabled:
                tw_cfg = self.config.sources.twitter
                if tw_cfg.mode == "playwright":
                    twitter_scraper = TwitterPlaywrightScraper(tw_cfg)
                else:
                    twitter_scraper = TwitterScraper(tw_cfg, client)
                tasks.append(self._fetch_with_progress("Twitter", twitter_scraper, since))

            # OSS Insight trending repos
            if self.config.sources.ossinsight and self.config.sources.ossinsight.enabled:
                oss_scraper = OSSInsightScraper(self.config.sources.ossinsight, client)
                tasks.append(self._fetch_with_progress("OSS Insight", oss_scraper, since))

            # GDELT 2.0 DOC API (key-less global news)
            if self.config.sources.gdelt and self.config.sources.gdelt.enabled:
                gdelt_scraper = GDELTScraper(self.config.sources.gdelt, client)
                tasks.append(self._fetch_with_progress("GDELT", gdelt_scraper, since))

            # Google News RSS (key-less news search)
            if self.config.sources.google_news and self.config.sources.google_news.enabled:
                gn_scraper = GoogleNewsScraper(self.config.sources.google_news, client)
                tasks.append(self._fetch_with_progress("Google News", gn_scraper, since))

            # Fetch all concurrently
            outcomes = await asyncio.gather(*tasks)
            self.last_fetch_report = FetchReport(outcomes=list(outcomes))

            # Flatten successful and empty outcomes; failures remain in the report.
            all_items: List[ContentItem] = []
            for outcome in outcomes:
                all_items.extend(outcome.items)

            return all_items

    async def _fetch_with_progress(
        self, name: str, scraper, since: datetime
    ) -> SourceFetchOutcome:
        """Fetch from a scraper with progress indication.

        Args:
            name: Source name for display
            scraper: Scraper instance
            since: Fetch items after this time

        Returns:
            SourceFetchOutcome: Named fetch result and diagnostics
        """
        self.console.print(f"{self.icons['fetch']} Fetching from {name}...")
        try:
            items = await scraper.fetch(since)
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            self.console.print(f"[red]   Failed to fetch {name}: {error}[/red]")
            return SourceFetchOutcome(
                source_name=name,
                status="failure",
                error=error,
            )

        self.console.print(f"   Found {len(items)} items from {name}")
        for item in items:
            item.metadata.setdefault("source_key", source_key(item))
        source_errors = dict(getattr(scraper, "source_errors", {}) or {})
        for key, error in sorted(source_errors.items()):
            self.console.print(f"[yellow]   {self.icons['warning']} {key}: {error}[/yellow]")

        # Show per-sub-source breakdown when there are multiple sub-sources
        sub_counts: Dict[str, int] = defaultdict(int)
        for item in items:
            sub_counts[self._sub_source_label(item)] += 1
        if len(sub_counts) > 1:
            for sub, count in sorted(sub_counts.items()):
                self.console.print(f"      {self.icons['detail']} {sub}: {count}")

        return SourceFetchOutcome(
            source_name=name,
            status="success" if items else "empty",
            items=items,
            source_errors=source_errors,
        )

    @staticmethod
    def _sub_source_label(item: ContentItem) -> str:
        """Return a human-readable sub-source label for an item."""
        meta = item.metadata
        if meta.get("subreddit"):
            return f"r/{meta['subreddit']}"
        if meta.get("feed_name"):
            return meta["feed_name"]
        if meta.get("channel"):
            return f"@{meta['channel']}"
        if meta.get("period") and meta.get("repo"):
            return f"ossinsight:{meta.get('primary_language', 'all')}"
        if meta.get("repo"):
            return meta["repo"]
        if meta.get("watchlist"):
            return meta["watchlist"]
        if meta.get("source_name"):
            return meta["source_name"]
        if meta.get("gn_query"):
            return f"google_news:{meta['gn_query']}"
        if meta.get("domain"):
            return meta["domain"]
        return item.author or "unknown"

    def merge_cross_source_duplicates(self, items: List[ContentItem]) -> List[ContentItem]:
        """Merge items that point to the same URL from different sources.

        This is a stable stage helper for integrations such as MCP.

        Keeps the item with the richest content and combines metadata.

        Args:
            items: Items to deduplicate

        Returns:
            List[ContentItem]: Deduplicated items
        """
        # Group by normalized URL
        url_groups: Dict[tuple[object, ...], List[ContentItem]] = {}
        for item in items:
            if isinstance(item.profile, list):
                requested_profile: object = tuple(
                    profile_id.strip() for profile_id in item.profile
                )
            else:
                requested_profile = (item.profile or "auto").strip() or "auto"
            key = (*_deduplication_url_key(str(item.url)), requested_profile)
            url_groups.setdefault(key, []).append(item)

        merged = []
        for group in url_groups.values():
            group_copies = [item.model_copy(deep=True) for item in group]
            if len(group) == 1:
                merged.append(group_copies[0])
                continue

            # Pick the item with the richest content as primary
            primary = max(group_copies, key=lambda x: len(x.content or ""))

            # Merge metadata and source info from other items
            all_sources = []
            for item in group_copies:
                if item.source_type.value not in all_sources:
                    all_sources.append(item.source_type.value)
                # Merge metadata (engagement, discussion, etc.)
                for mk, mv in item.metadata.items():
                    if mk not in primary.metadata or not primary.metadata[mk]:
                        primary.metadata[mk] = mv

                # Append content (e.g., comments from another source)
                if item is not primary and item.content:
                    if primary.content and item.content not in primary.content:
                        primary.content = (primary.content or "") + f"\n\n--- From {item.source_type.value} ---\n" + item.content

            primary.metadata["merged_sources"] = all_sources
            merged.append(primary)

        return merged

    async def merge_topic_duplicates(
        self,
        items: List[ContentItem],
        *,
        log: bool = True,
        references: Sequence[ContentItem] = (),
    ) -> List[ContentItem]:
        """Merge items covering the same topic using AI semantic deduplication.

        This is a stable stage helper for integrations such as MCP.

        Sends all item titles, tags, and summaries to AI in a single call.
        Items must already be sorted by analysis score descending so that the first
        item in each duplicate group is always the highest-scored one.
        Content (comments) from duplicate items is merged into the primary.

        ``references`` are other reports (below the threshold, or from earlier runs
        in the archive) listed after the items: they are never kept or dropped, but
        a reference grouped with an item adds its URL to the item's corroborating
        URLs. Only official or reputable publishers are worth passing.

        Falls back to returning items unchanged if the AI call fails.
        """
        if not items or (len(items) <= 1 and not references):
            return items

        from .ai.prompting.deduplication import (
            TOPIC_DEDUP_REFERENCES,
            TOPIC_DEDUP_SYSTEM,
            TOPIC_DEDUP_USER,
        )
        from .ai.utils import parse_json_response

        # Build the item list for the prompt
        lines = []
        for i, item in enumerate([*items, *references]):
            analysis = item.processing.analysis if item.processing else None
            tags = ", ".join(analysis.tags) if analysis and analysis.tags else "—"
            summary = analysis.summary if analysis else "—"
            marker = " (reference)" if i >= len(items) else ""
            lines.append(f"[{i}]{marker} {item.title}\n    Tags: {tags}\n    Summary: {summary}")
        items_text = "\n\n".join(lines)
        if references:
            items_text += "\n\n" + TOPIC_DEDUP_REFERENCES

        try:
            ai_client = create_ai_client(self.config.ai)
            response = await ai_client.complete(
                system=TOPIC_DEDUP_SYSTEM,
                user=TOPIC_DEDUP_USER.format(items=items_text),
            )
            result = parse_json_response(response)
            if result is None:
                if log:
                    self.console.print("[yellow]  dedup: could not parse AI response, skipping[/yellow]")
                return items

            duplicate_groups = result.get("duplicates", [])
        except Exception as e:
            if log:
                self.console.print(f"[yellow]  dedup: AI call failed ({e}), skipping[/yellow]")
            return items

        if not duplicate_groups:
            return items

        # Build a set of indices to drop (all non-primary duplicates)
        drop_indices: set[int] = set()
        for group in duplicate_groups:
            if not isinstance(group, list) or len(group) < 2:
                continue
            indices = [index for index in group if isinstance(index, int) and not isinstance(index, bool)]
            members = [index for index in indices if 0 <= index < len(items)]
            if not members:
                continue  # references only: nothing to keep or drop
            primary_idx = members[0]
            primary = items[primary_idx]
            for ref_idx in indices:
                if len(items) <= ref_idx < len(items) + len(references):
                    reference = references[ref_idx - len(items)]
                    corroborating = primary.metadata.setdefault("corroborating_urls", [])
                    if str(reference.url) != str(primary.url) and str(reference.url) not in corroborating:
                        corroborating.append(str(reference.url))
                        if log:
                            self.console.print(
                                f"   [dim]corroboration: [{primary_idx}] {primary.title}[/dim]\n"
                                f"   [dim]       also reported by {reference.url}[/dim]"
                            )
            for dup_idx in members[1:]:
                if dup_idx == primary_idx:
                    continue
                dup = items[dup_idx]
                # Keep the duplicate's URLs: independent reports corroborate the primary.
                corroborating = primary.metadata.setdefault("corroborating_urls", [])
                for url in [str(dup.url), *(dup.metadata.get("corroborating_urls") or [])]:
                    if url != str(primary.url) and url not in corroborating:
                        corroborating.append(url)
                # Merge comments/content from the duplicate into the primary
                if dup.content:
                    if not primary.content or dup.content not in primary.content:
                        label = dup.source_type.value
                        primary.content = (primary.content or "") + f"\n\n--- From {label} ---\n{dup.content}"
                if log:
                    self.console.print(
                        f"   [dim]dedup: keep [{primary_idx}] {primary.title}[/dim]\n"
                        f"   [dim]       drop [{dup_idx}] {dup.title}[/dim]"
                    )
                drop_indices.add(dup_idx)

        return [item for i, item in enumerate(items) if i not in drop_indices]

    async def filter_items(
        self,
        items: List[ContentItem],
        *,
        threshold: Optional[float] = None,
        topic_dedup: bool = True,
        apply_balance: bool = True,
        log: bool = True,
    ) -> FilteringPipelineResult:
        """Apply score thresholding, optional topic dedup, and digest balancing."""
        threshold_items = []
        for item in items:
            if self.passes_profile_filter(item, threshold):
                threshold_items.append(item)
        threshold_items.sort(
            key=self._rank_key,
            reverse=True,
        )

        if log:
            self.console.print(
                f"{self.icons['filter']} Selected {len(threshold_items)} items "
                "with profile filters\n"
            )

        deduped_items = threshold_items
        references = self._corroboration_references(threshold_items, items)
        if topic_dedup and deduped_items:
            profile_groups: Dict[str, List[ContentItem]] = defaultdict(list)
            for item in deduped_items:
                profile_id = (
                    item.processing.classification.profile
                    if item.processing
                    else self.profiles.default_profile
                )
                profile_groups[profile_id].append(item)
            deduped_items = []
            for profile_id, profile_items in profile_groups.items():
                settings = self.config.processing.profile_settings.get(profile_id)
                if settings is None or settings.topic_dedup:
                    # References only when there are some: overrides of this stage
                    # (tests, integrations) may not accept them.
                    extra = {"references": references[profile_id]} if references.get(profile_id) else {}
                    deduped_items.extend(
                        await self.merge_topic_duplicates(profile_items, log=log, **extra)
                    )
                else:
                    deduped_items.extend(profile_items)
            deduped_items.sort(
                key=self._rank_key,
                reverse=True,
            )
        topic_dedup_removed = len(threshold_items) - len(deduped_items)
        self._apply_corroboration(deduped_items)

        if log and topic_dedup_removed:
            self.console.print(
                f"{self.icons['cleanup']} Removed {topic_dedup_removed} topic duplicates "
                f"→ {len(deduped_items)} unique items\n"
            )

        balanced_digest = (
            self.apply_balanced_digest(deduped_items, log=log)
            if apply_balance
            else BalancedDigestResult(items=deduped_items)
        )
        return FilteringPipelineResult(
            items=balanced_digest.items,
            threshold_count=len(threshold_items),
            topic_dedup_count=len(deduped_items),
            topic_dedup_removed=topic_dedup_removed,
            balanced_digest=balanced_digest,
        )

    async def select_digest_items(
        self,
        items: List[ContentItem],
        *,
        threshold: Optional[float] = None,
        topic_dedup: bool = True,
        log: bool = True,
    ) -> FilteringPipelineResult:
        """Select final digest items using the same stages for every entry point."""
        initial = await self.filter_items(
            items,
            threshold=threshold,
            topic_dedup=topic_dedup,
            apply_balance=False,
            log=log,
        )
        candidates = initial.items
        await self._expand_twitter_discussion(candidates)

        # Targeted re-analysis can lower a score, so reapply profile filters.
        eligible = [
            item
            for item in candidates
            if self.passes_profile_filter(item, threshold)
        ]
        eligible.sort(
            key=self._rank_key,
            reverse=True,
        )
        balanced = self.apply_balanced_digest(eligible, log=log)
        return FilteringPipelineResult(
            items=balanced.items,
            threshold_count=initial.threshold_count,
            topic_dedup_count=initial.topic_dedup_count,
            topic_dedup_removed=initial.topic_dedup_removed,
            balanced_digest=balanced,
            eligible_count=len(eligible),
        )

    def passes_profile_filter(
        self,
        item: ContentItem,
        threshold: Optional[float] = None,
    ) -> bool:
        if not item.processing or not item.processing.analysis:
            return False
        score = item.processing.analysis.score
        if score is None:
            # The AI could not score this item; never publish it unreviewed.
            return False
        digest = getattr(self.config, "digest", None)
        if getattr(digest, "only_watched_categories", False):
            # Only the domains the reader follows (the AI's categories decide).
            if not set(digest.watched_categories) & set(item.processing.analysis.categories):
                return False
        reliability_config = getattr(self.config, "reliability", None)
        reliability = item.processing.reliability
        if (
            reliability_config is not None
            and reliability is not None
            and reliability.label in reliability_config.exclude_labels
        ):
            return False
        profile_id = item.processing.classification.profile
        settings = self.config.processing.profile_settings.get(profile_id)
        effective_threshold = threshold
        if effective_threshold is None and settings is not None:
            effective_threshold = settings.threshold
        if effective_threshold is None:
            return True
        return score >= effective_threshold

    def _apply_corroboration(self, items: List[ContentItem]) -> None:
        """Re-assess reliability of items that absorbed reports from other publishers."""
        policy = getattr(self, "reliability_policy", None) or ReliabilityPolicy()
        for item in items:
            if item.processing and item.metadata.get("corroborating_urls"):
                item.processing.reliability = assess_item(item, policy)

    def apply_balanced_digest(
        self,
        items: List[ContentItem],
        *,
        log: bool = True,
    ) -> BalancedDigestResult:
        """Apply configured category quotas and the final item cap.

        Categories are read from ``item.metadata["category"]``. If a category
        appears in more than one configured group, the first group in config
        order wins.
        """
        digest = self.config.digest
        groups = digest.category_groups
        max_items = digest.max_items

        if not groups and max_items is None:
            return BalancedDigestResult(items=items)

        sorted_items = sorted(
            items,
            key=self._rank_key,
            reverse=True,
        )

        category_to_group: Dict[str, str] = {}
        duplicate_categories: List[str] = []
        for group_key, group in groups.items():
            for category in group.categories:
                if category in category_to_group:
                    if category_to_group[category] != group_key:
                        duplicate_categories.append(category)
                    continue
                category_to_group[category] = group_key

        if log:
            for category in sorted(set(duplicate_categories)):
                first_group = category_to_group[category]
                self.console.print(
                    f"[yellow]Warning: category '{category}' is configured in multiple "
                    f"groups; using '{first_group}'.[/yellow]"
                )

        selected: List[tuple[ContentItem, str]] = []
        group_counts: Dict[str, int] = defaultdict(int)
        default_group = digest.default_group

        for item in sorted_items:
            category = item.metadata.get("category")
            group_key = (
                category_to_group.get(category, default_group)
                if isinstance(category, str)
                else default_group
            )

            if group_key in groups:
                limit = groups[group_key].limit
            else:
                limit = digest.default_group_limit

            if limit is not None and group_counts[group_key] >= limit:
                continue

            selected.append((item, group_key))
            group_counts[group_key] += 1

        if max_items is not None:
            selected = selected[:max_items]

        final_counts: Dict[str, int] = defaultdict(int)
        for _, group_key in selected:
            final_counts[group_key] += 1

        group_limits: Dict[str, Optional[int]] = {
            group_key: group.limit for group_key, group in groups.items()
        }
        group_limits.setdefault(default_group, digest.default_group_limit)

        if log:
            self.console.print(
                f"{self.icons['balance']} Balanced digest selected "
                f"{len(selected)}/{len(items)} items"
            )
            for group_key, group in groups.items():
                label = group.name or group_key
                self.console.print(
                    f"      {self.icons['detail']} {label}: "
                    f"{final_counts.get(group_key, 0)}/{group.limit}"
                )
            if (
                final_counts.get(default_group, 0)
                or digest.default_group_limit is not None
            ):
                limit_label = (
                    str(digest.default_group_limit)
                    if digest.default_group_limit is not None
                    else "unlimited"
                )
                self.console.print(
                    f"      {self.icons['detail']} {default_group}: "
                    f"{final_counts.get(default_group, 0)}/{limit_label}"
                )
            self.console.print("")

        return BalancedDigestResult(
            items=[item for item, _ in selected],
            enabled=True,
            group_counts=dict(final_counts),
            group_limits=group_limits,
            duplicate_categories=sorted(set(duplicate_categories)),
        )

    async def _expand_twitter_discussion(self, items: List[ContentItem]) -> None:
        """Second-stage: fetch reply text for important Twitter items and re-analyze.

        Only runs when sources.twitter.fetch_reply_text is True.
        Bounded by max_tweets_to_expand to control cost.
        """
        tw_cfg = self.config.sources.twitter
        if not tw_cfg or not tw_cfg.enabled or not tw_cfg.fetch_reply_text:
            return

        from .models import SourceType

        twitter_items = [
            item for item in items
            if item.source_type == SourceType.TWITTER
        ][:tw_cfg.max_tweets_to_expand]

        if not twitter_items:
            return

        self.console.print(
            f"{self.icons['discussion']} Fetching reply text for "
            f"{len(twitter_items)} Twitter items..."
        )

        async with httpx.AsyncClient(timeout=30.0) as client:
            if tw_cfg.mode == "playwright":
                self.console.print(
                    "   [yellow]Reply expansion not yet supported in Playwright mode.[/yellow]"
                )
                return
            scraper = TwitterScraper(tw_cfg, client)
            expanded = []
            for item in twitter_items:
                try:
                    reply_lines = await scraper.fetch_replies_for_item(item)
                    if TwitterScraper.append_discussion_content(item, reply_lines):
                        expanded.append(item)
                        self.console.print(
                            f"   {self.icons['discussion']} {len(reply_lines)} replies "
                            f"added to: {item.title[:60]}"
                        )
                except Exception as exc:
                    self.console.print(
                        f"   [yellow]{self.icons['warning']} Reply fetch failed for "
                        f"{item.id}: {exc}[/yellow]"
                    )

        if not expanded:
            return

        self.console.print(
            f"   Re-analyzing {len(expanded)} Twitter items with reply context...\n"
        )
        ai_client = create_ai_client(self.config.ai)
        analyzer = ContentAnalyzer(
            ai_client,
            self.profiles,
            console=self.console,
            reliability_policy=self.reliability_policy,
        )
        await analyzer.analyze_batch(expanded)

    async def enrich_items(self, items: List[ContentItem]) -> EnrichmentBatchResult:
        """Enrich items with background knowledge (2nd AI pass).

        For each item that passed the score threshold, call AI to generate
        background knowledge based on the item's actual content.

        Args:
            items: Important items to enrich (modified in-place)
        """
        if not items:
            return EnrichmentBatchResult()

        self.console.print(
            f"{self.icons['enrich']} Enriching with background knowledge..."
        )
        reused = self._reusable_enrichments(items)
        if reused:
            self.console.print(
                f"   {self.icons['detail']} Reused {len(reused)} enrichments from the archive"
            )
            items = [item for item in items if item.id not in reused]
            if not items:
                self.console.print("")
                return EnrichmentBatchResult(succeeded_ids=list(reused))
        ai_client = create_ai_client(self.config.ai)
        enricher = ContentEnricher(
            ai_client,
            self.profiles,
            self.config.ai.languages,
            console=self.console,
            tools=ToolRegistry(self.storage.summaries_dir),
        )
        result = await enricher.enrich_batch(items)
        failed = [item for item in items if item.id in result.failures]
        if await self._pause_before_retry(len(failed), "enrichment"):
            retry = await enricher.enrich_batch(failed)
            result = EnrichmentBatchResult(
                succeeded_ids=result.succeeded_ids + retry.succeeded_ids,
                failures=retry.failures,
            )
        self.console.print(
            f"   Enriched {result.succeeded_count}/{len(items)} items"
        )
        result.succeeded_ids = list(reused) + result.succeeded_ids
        if budget.exhausted() is not None and result.failed_count:
            self.console.print(
                f"   [yellow]AI quota exhausted: {result.failed_count} item(s) keep their "
                "analysis, without enrichment[/yellow]"
            )
        elif result.failed_count:
            self.console.print(
                f"   [yellow]Skipped {result.failed_count} items after enrichment "
                f"failed: {', '.join(result.failed_ids)}[/yellow]"
            )
        self.console.print("")
        return result

    async def analyze_items(self, items: List[ContentItem]) -> List[ContentItem]:
        """Analyze content items with AI.

        Args:
            items: Items to analyze

        Returns:
            List[ContentItem]: Analyzed items
        """
        self.console.print(f"{self.icons['ai']} Analyzing content with AI...")

        to_analyze = self._reuse_archived_analyses(items)
        if not to_analyze:
            return items

        ai_client = create_ai_client(self.config.ai)
        analyzer = ContentAnalyzer(
            ai_client,
            self.profiles,
            console=self.console,
            reliability_policy=self.reliability_policy,
        )

        await analyzer.analyze_batch(to_analyze)

        failed = [item for item in to_analyze if self._is_unscored(item)]
        if await self._pause_before_retry(len(failed), "analysis"):
            await analyzer.analyze_batch(failed)

        skipped = sum(bool(item.processing and item.processing.ai_skipped) for item in items)
        unscored = sum(self._is_unscored(item) for item in items) - skipped
        if skipped:
            limit = budget.exhausted()
            reason = (
                "token budget for this run reached"
                if limit is budget.AILimit.TOKEN_BUDGET
                else "provider quota exhausted"
            )
            self.console.print(
                f"[yellow]{self.icons['warning']} AI unavailable ({reason}): {skipped} item(s) "
                "not analyzed; they are retried in the next run[/yellow]"
            )
        if unscored:
            self.console.print(
                f"[yellow]{self.icons['warning']} {unscored} item(s) could not be scored "
                "and are left out of this digest[/yellow]"
            )
        return items

    def _reusable_enrichments(self, items: List[ContentItem]) -> List[str]:
        """Ids of items that already carry an enrichment in every configured language.

        Only an analysis reused from the archive keeps its artifacts (a new analysis
        clears them), so these are unchanged items enriched in an earlier run.
        """
        settings = getattr(self.config, "archive", None)
        if settings is None or not settings.reuse_enrichment:
            return []
        languages = set(self.config.ai.languages)
        return [
            item.id
            for item in items
            if item.processing and languages <= set(item.processing.artifacts)
        ]

    def _rank_key(self, item: ContentItem) -> tuple[float, float]:
        """Digest order: AI score first; source quality only breaks ties."""
        analysis = item.processing.analysis if item.processing else None
        score = analysis.score if analysis and analysis.score is not None else -1
        quality = getattr(self, "source_quality", {}).get(item_source_key(item), 0.5)
        return score, quality

    def _load_archive_signals(self, run_items: List[ContentItem]) -> None:
        """Load source quality and earlier reports from the archive (best effort)."""
        self.source_quality = {}
        self.archived_references = []
        archive = getattr(self, "archive", None)
        if archive is None:
            return
        now = datetime.now(timezone.utc)
        days = self.config.digest.source_quality_days
        lookback = self.config.reliability.corroboration_lookback_hours
        try:
            if days:
                history = archive.items_between(now - timedelta(days=days))
                self.source_quality = {
                    key: quality.score
                    for key, quality in compute_source_quality(
                        history, self.reliability_policy
                    ).items()
                }
            if lookback and self.config.reliability.corroboration_max_references:
                current = {item.id for item in run_items}
                self.archived_references = [
                    item
                    for item in archive.items_between(now - timedelta(hours=lookback))
                    if item.id not in current
                ]
        except Exception as exc:
            logger.warning("Could not load archive signals: %s", exc)

    def _corroboration_references(
        self, candidates: List[ContentItem], analyzed: List[ContentItem]
    ) -> Dict[str, List[ContentItem]]:
        """Per profile, other official/reputable reports that may corroborate candidates.

        Analyzed items of this run left out of the candidates (below the threshold)
        and archived items from the lookback window, most recent first.
        """
        reliability_config = getattr(self.config, "reliability", None)
        limit = getattr(reliability_config, "corroboration_max_references", 0)
        if not limit:
            return {}
        policy = getattr(self, "reliability_policy", None) or ReliabilityPolicy()
        candidate_ids = {item.id for item in candidates}
        seen: set[str] = set()
        by_profile: Dict[str, List[ContentItem]] = defaultdict(list)
        pool = [*analyzed, *getattr(self, "archived_references", [])]
        pool.sort(key=lambda item: item.published_at, reverse=True)
        for item in pool:
            if item.id in candidate_ids or item.id in seen:
                continue
            analysis = item.processing.analysis if item.processing else None
            if analysis is None or analysis.score is None:
                continue
            tier = source_tier_for(item, policy)[0]
            if tier not in (SourceTier.OFFICIAL, SourceTier.REPUTABLE):
                continue
            profile_refs = by_profile[item.processing.classification.profile]
            if len(profile_refs) < limit:
                seen.add(item.id)
                profile_refs.append(item)
        return dict(by_profile)

    # SourceTier is declared from most to least trusted.
    _TIER_ORDER = {tier: rank for rank, tier in enumerate(SourceTier)}

    def select_unanalyzed_items(self, items: List[ContentItem]) -> List[ContentItem]:
        """Items left unanalyzed because the AI quota ran out, to publish apart.

        Only when the quota ran out during this run (any other analysis failure keeps
        an item out of the digest). Best-known publishers first, then most recent;
        reliability exclusions still apply (these items are always "unverified").
        """
        if budget.exhausted() is None:
            return []
        limit = getattr(getattr(self.config, "digest", None), "unanalyzed_max_items", 15)
        reliability_config = getattr(self.config, "reliability", None)
        excluded = set(reliability_config.exclude_labels if reliability_config else [])
        skipped = [
            item
            for item in items
            if item.processing
            and item.processing.ai_skipped
            and item.processing.reliability is not None
            and item.processing.reliability.label not in excluded
        ]
        skipped.sort(
            key=lambda item: (
                self._TIER_ORDER[item.processing.reliability.source_tier],
                -item.published_at.timestamp(),
            )
        )
        selected = skipped[:limit] if limit else []
        if selected:
            self.console.print(
                f"{self.icons['warning']} Publishing {len(selected)} item(s) without AI "
                "analysis in a separate section\n"
            )
        return selected

    @staticmethod
    def _is_unscored(item: ContentItem) -> bool:
        analysis = item.processing.analysis if item.processing else None
        return analysis is None or analysis.score is None

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
