#!/bin/bash

set -euo pipefail

PROJECT_DIR="/workspace/apartment-agent"

cd "$PROJECT_DIR"

OUTPUT="$(
    python3 run.py --alerts-only
)"

if [ "$OUTPUT" = "NO_ALERTS" ]; then
    exit 0
fi

printf '%s\n' "$OUTPUT"