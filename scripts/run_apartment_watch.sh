#!/bin/bash

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "$PROJECT_DIR"

OUTPUT="$(
    python3 run.py --alerts-only
)"

python3 scripts/generate_watchlist.py

if [ "$OUTPUT" = "NO_ALERTS" ]; then
    exit 0
fi

printf '%s\n' "$OUTPUT"
printf '%s\n' "$OUTPUT" | python3 scripts/send_telegram_alerts.py

ALERT_IDS="$(printf '%s\n' "$OUTPUT" | sed -n 's/^\[ALERT_ID=\([0-9][0-9]*\)\].*/\1/p' | paste -sd ' ' -)"
if [ -n "$ALERT_IDS" ] && [ -n "${TELEGRAM_BOT_TOKEN:-}" ] && [ -n "${TELEGRAM_CHAT_ID:-}" ]; then
    python3 run.py --mark-alerts-delivered $ALERT_IDS
fi
