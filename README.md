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
