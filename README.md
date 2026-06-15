# 1,000 Days

> Read one short story, one poem, and one essay every day for 1,000 days.
> — Ray Bradbury

A static site serving one short story, poem, and essay per day — public domain in-app,
or a contemporary pick from Electric Literature (stories) and NYT Magazine (essays).
All works are real, curated, and sourced from Project Gutenberg, Standard Ebooks,
PoetryDB, Electric Literature, and the New York Times. Nothing is AI-generated.

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

**Public domain (in-app reading)**
- **Poems**: [PoetryDB](https://poetrydb.org) — 1,306 poems
- **Stories**: [Project Gutenberg](https://gutenberg.org) + [Standard Ebooks](https://standardebooks.org) — 2,506 stories
- **Essays**: Gutenberg + Standard Ebooks — 1,048 essays

All public-domain works are US public domain (published before 1928).

**Contemporary picks (link out, cached locally)**
- **Stories**: [Electric Literature](https://electricliterature.com) — 1,166 posts cached
- **Essays**: [NYT Magazine](https://nytimes.com/section/magazine) — 900 articles, 1995–2024

Refresh caches with `python scripts/refresh_cache.py`.
