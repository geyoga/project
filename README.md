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
page after each successful crawl. The expected interval defaults to six hours;
override it with `WATCHLIST_UPDATE_INTERVAL_MINUTES` when the Hermes schedule
uses another interval.
