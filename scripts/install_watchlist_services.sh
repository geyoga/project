#!/bin/bash

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
UNIT_DIR="$HOME/.config/systemd/user"

mkdir -p "$UNIT_DIR"
mkdir -p "$HOME/.config/apartment-agent"

for unit in apartment-watchlist.service apartment-watch.service apartment-watch.timer; do
    sed "s|%h/apartment-agent|$PROJECT_DIR|g" \
        "$PROJECT_DIR/deploy/systemd/$unit" \
        > "$UNIT_DIR/$unit"
done

systemctl --user daemon-reload
systemctl --user enable --now apartment-watchlist.service
systemctl --user enable --now apartment-watch.timer

printf 'Watchlist: http://%s:1221\n' "$(hostname -I | awk '{print $1}')"
systemctl --user --no-pager status apartment-watchlist.service
systemctl --user list-timers apartment-watch.timer
