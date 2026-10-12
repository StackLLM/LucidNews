"""Selection: score threshold, profile filter, balanced digest and the items left unanalyzed."""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
import logging

from ..models import ContentItem
from ..ai import budget
from ..reliability.assess import ReliabilityPolicy, assess_item, source_tier_for
from ..reliability.models import SourceTier
from ..source_quality import compute_source_quality, item_source_key


logger = logging.getLogger(__name__)


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


class SelectionMixin:
    """Selection: score threshold, profile filter, balanced digest and the items left unanalyzed."""

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
