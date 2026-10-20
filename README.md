# Apartment Agent

A command-line apartment crawler and notifier for Japanese rental listings.

## Current sources

- UR rental listings are crawled from configured area codes.
- SUUMO/CHINTAI processing is supported through incoming normalized JSON files.

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/playwright install chromium
```

## Configuration

Edit `config/search_profile.json`. Runtime files are stored in `data/` by default.
The locations can be overridden with `APARTMENT_AGENT_DATA_DIR`,
`APARTMENT_AGENT_CONFIG_DIR`, `APARTMENT_AGENT_DB`, and
`APARTMENT_AGENT_INCOMING_DIR`.

## Run

```bash
.venv/bin/python run.py
.venv/bin/python run.py --alerts-only
.venv/bin/python -m unittest discover -s tests -v
```

`data/apartments.db`, caches, and incoming listing JSON files are runtime data;
back them up before migrations or cleanup.
