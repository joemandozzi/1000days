"""
Daily external picks loaded from local cache files:
  cache/el_stories.json   — Electric Literature posts
  cache/nyt_essays.json   — NYT Magazine articles

Run scripts/refresh_cache.py to rebuild the cache.
Falls back to None if cache files are missing.
"""
import json
import random
from datetime import date
from pathlib import Path

CACHE_DIR = Path(__file__).parent / "cache"


def _load(filename):
    path = CACHE_DIR / filename
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def get_external_picks(target_date=None):
    """
    Returns {'story': {...} | None, 'essay': {...} | None}.
    Each dict has: title, author, excerpt, url, source_name.
    Pick is deterministic for a given date.
    """
    if target_date is None:
        target_date = date.today()

    rng = random.Random(target_date.isoformat() + ":external")

    el_stories  = _load("el_stories.json")
    nyt_essays  = _load("nyt_essays.json")

    return {
        "story": rng.choice(el_stories)  if el_stories  else None,
        "essay": rng.choice(nyt_essays)  if nyt_essays  else None,
    }
