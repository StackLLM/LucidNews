#!/usr/bin/env bash
# LucidNews daily run.
# Usage: ./scripts/daily-run.sh [hours]
# Cron:  0 7 * * * /path/to/LucidNews/scripts/daily-run.sh >> /path/to/LucidNews/logs/cron.log 2>&1

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
HOURS="${1:-24}"
LOG_PREFIX="[$(date '+%Y-%m-%d %H:%M:%S')]"

cd "$PROJECT_DIR"
mkdir -p logs

echo "$LOG_PREFIX Starting LucidNews daily run (last ${HOURS}h)..."
uv sync --quiet
uv run lucidnews --hours "$HOURS"
echo "$LOG_PREFIX Done."
