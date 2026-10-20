#!/bin/bash

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "$PROJECT_DIR"

OUTPUT="$(
    python3 run.py --alerts-only
)"

if [ "$OUTPUT" = "NO_ALERTS" ]; then
    exit 0
fi

printf '%s\n' "$OUTPUT"
