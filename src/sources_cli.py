"""CLI: source health report from the run archive (``lucidnews-sources``)."""

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from rich.console import Console
from rich.table import Table

from ._cli import add_data_dir_arguments
from .archive import ItemArchive
from .source_health import HealthStatus, assess_health, configured_source_keys, health_to_dict
from .storage.manager import StorageManager

STATUS_STYLES = {
    HealthStatus.DEAD: "bold red",
    HealthStatus.FAILING: "red",
    HealthStatus.SILENT: "yellow",
    HealthStatus.NOISY: "yellow",
    HealthStatus.HEALTHY: "green",
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="LucidNews source health report")
    parser.add_argument("--days", type=int, default=14, help="Window in days (default: 14)")
    parser.add_argument(
        "--status",
        choices=[status.value for status in HealthStatus],
        action="append",
        help="Only show these statuses (repeatable)",
    )
    parser.add_argument("--json", action="store_true", help="Print JSON instead of a table")
    parser.add_argument(
        "--all",
        action="store_true",
        help="Include sources that are no longer configured",
    )
    add_data_dir_arguments(parser)
    args = parser.parse_args(argv)
    console = Console()

    storage = StorageManager(data_dir=args.data_dir, config_path=args.config)
    archive_path = Path(args.data_dir) / "archive.sqlite3"
    configured: dict[str, str] = {}
    try:
        config = storage.load_config()
        archive_path = Path(config.archive.path)
        if not archive_path.is_absolute():
            archive_path = Path(args.data_dir) / archive_path
        configured = configured_source_keys(config)
    except FileNotFoundError:
        pass
    if not archive_path.exists():
        console.print(f"[yellow]No archive at {archive_path}. Run `uv run lucidnews` first.[/yellow]")
        return 1

    since = datetime.now(timezone.utc) - timedelta(days=args.days)
    report = assess_health(ItemArchive(archive_path).source_run_rows(since))
    never_seen = sorted(set(configured) - {health.source_key for health in report})
    if configured and not args.all:
        report = [health for health in report if health.source_key in configured]
    if args.status:
        report = [health for health in report if health.status.value in args.status]

    if args.json:
        print(
            json.dumps(
                {
                    "days": args.days,
                    "sources": [health_to_dict(h) for h in report],
                    "configured_without_history": never_seen,
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        return 0

    table = Table(title=f"Source health — last {args.days} days")
    for column in ("Source", "Status", "Runs", "Failures", "Items/run", "Selected", "Last success", "Detail"):
        table.add_column(column, justify="right" if column in {"Runs", "Failures", "Items/run", "Selected"} else "left")
    for h in report:
        detail = "; ".join(h.reasons)
        if h.last_error and h.status in (HealthStatus.DEAD, HealthStatus.FAILING):
            detail = f"{detail} — {h.last_error}" if detail else h.last_error
        table.add_row(
            h.source_key,
            f"[{STATUS_STYLES[h.status]}]{h.status.value}[/]",
            str(h.runs),
            str(h.failures),
            f"{h.items_per_run:.1f}",
            f"{h.selected} ({h.selection_rate:.0%})" if h.items else "0",
            (h.last_success_at or "never")[:16].replace("T", " "),
            detail,
        )
    console.print(table)
    if never_seen:
        console.print(
            f"[dim]{len(never_seen)} configured source(s) have no history yet: "
            f"{', '.join(never_seen)}[/dim]"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
