# 1,000 Nights

> Read one short story, one poem, and one essay every night for 1,000 nights.
> — Ray Bradbury

A static site serving one public-domain short story, poem, and essay per day.
All works are real, curated, and sourced from Project Gutenberg, Standard Ebooks,
and PoetryDB. Nothing is AI-generated.

## Setup

```bash
# 1. Install Python 3.12 (requires Homebrew)
brew install python@3.12

# 2. Create and activate a virtual environment
python3.12 -m venv .venv
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt
```

## Usage

```bash
# Populate the database (run once, then as needed)
python ingest/poems.py
python ingest/stories.py
python ingest/essays.py

# Build the site for today
python build.py

# Build for a specific date
python build.py 2026-06-10

# Open the result
open site/index.html
```

## Project structure

```
corpus/     — SQLite database and helper functions
ingest/     — scripts that pull works from external sources
templates/  — Jinja2 HTML templates
static/     — CSS and the streak counter JS
site/       — generated output (git-ignored)
build.py    — static site generator entry point
picker.py   — date-seeded daily selection logic
```

## Content sources

- **Poems**: [PoetryDB](https://poetrydb.org) — ~3,000 public-domain poems
- **Stories**: [Project Gutenberg](https://gutenberg.org) via Gutendex API
- **Essays**: Harvard Classics vols. 27–28 (Gutenberg) + Standard Ebooks

All works are US public domain (published ≤ 1930).
