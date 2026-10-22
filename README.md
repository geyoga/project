# Apartment Agent

A command-line apartment crawler and notifier for Japanese rental listings.

## Current sources

- UR rental listings are the only active source.

## Setup

```bash
python3 -m venv .venv
.venv/bin/python -m unittest discover -s tests -v
```

## Configuration

Edit `config/search_profile.json`. Runtime files are stored in `data/` by default.
The locations can be overridden with `APARTMENT_AGENT_DATA_DIR`,
`APARTMENT_AGENT_CONFIG_DIR` and `APARTMENT_AGENT_DB`.

## Run

```bash
.venv/bin/python run.py
.venv/bin/python run.py --alerts-only
.venv/bin/python -m unittest discover -s tests -v
```

`data/apartments.db` and cache files are runtime data. Back them up before
migrations or cleanup.

`listings` contains availability history. Query the `current_listings` SQLite
view when you need only rooms verified available by the latest successful crawl.

## Watchlist

Generate the mobile-friendly static watchlist from current listings:

```bash
python3 scripts/generate_watchlist.py
python3 -m http.server 1221 --directory watchlist
```

Then open `http://localhost:1221`. The scheduled watch script regenerates the
page after each successful crawl. The expected interval defaults to three hours;
override it with `WATCHLIST_UPDATE_INTERVAL_MINUTES` when the Hermes schedule
uses another interval.

### Run autonomously on Hermes (systemd)

On the Hermes machine, from the project directory:

```bash
chmod +x scripts/install_watchlist_services.sh
scripts/install_watchlist_services.sh
loginctl enable-linger "$USER"
```

This starts the static server on port `1221` and refreshes UR data every three
hours in the Hermes machine's local timezone. Set that machine to `Asia/Jakarta`
if these should be Jakarta times. Check it with:

```bash
systemctl --user status apartment-watchlist.service
systemctl --user list-timers apartment-watch.timer
journalctl --user -u apartment-watch.service -n 100 --no-pager
```

### Telegram alerts

Create the systemd environment file on Hermes:

```bash
mkdir -p ~/.config/apartment-agent
cat > ~/.config/apartment-agent/telegram.env <<'EOF'
TELEGRAM_BOT_TOKEN=your-bot-token
TELEGRAM_CHAT_ID=your-chat-id
EOF
chmod 600 ~/.config/apartment-agent/telegram.env
systemctl --user restart apartment-watch.timer
```

The scheduled job sends pending new, returned, and qualifying price-change
alerts to Telegram. Alerts are marked delivered only after Telegram accepts the
message. If credentials are absent, crawling and watchlist generation continue
without Telegram delivery.

The server binds to the local network. Do not expose port 1221 publicly; use a
private network such as Tailscale when accessing it away from home.
