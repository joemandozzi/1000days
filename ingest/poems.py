"""
Ingest poems from PoetryDB (poetrydb.org).

Fetches poems by a curated list of public-domain authors.
Run: python ingest/poems.py
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import requests
from corpus.db import init_db, insert_work, count_by_type

# Authors confirmed public domain via PoetryDB.
# PoetryDB uses author names exactly as shown; these are the canonical spellings.
POETS = [
    "Emily Dickinson",
    "Walt Whitman",
    "William Blake",
    "John Keats",
    "Percy Bysshe Shelley",
    "Alfred Lord Tennyson",
    "Robert Browning",
    "Christina Rossetti",
    "Gerard Manley Hopkins",
    "Edgar Allan Poe",
    "Henry Wadsworth Longfellow",
    "Ralph Waldo Emerson",
    "William Wordsworth",
    "Samuel Taylor Coleridge",
    "Lord Byron",
    "Matthew Arnold",
    "Thomas Hardy",
    "A.E. Housman",
    "Rudyard Kipling",
    "William Butler Yeats",
    "Rupert Brooke",
]


BASE_URL = "https://poetrydb.org"


def fetch_poems_by_author(author: str) -> list[dict]:
    url = f"{BASE_URL}/author/{requests.utils.quote(author)}"
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    if isinstance(data, dict) and data.get("status") == 404:
        return []
    return data if isinstance(data, list) else []


def ingest_poems():
    init_db()
    total = 0
    for poet in POETS:
        print(f"  Fetching {poet}...", end=" ", flush=True)
        try:
            poems = fetch_poems_by_author(poet)
        except Exception as e:
            print(f"ERROR: {e}")
            continue

        count = 0
        for p in poems:
            title = p.get("title", "").strip()
            lines = p.get("lines", [])
            if not title or not lines:
                continue
            text = "\n".join(lines)
            word_count = len(text.split())
            insert_work(
                type="poem",
                title=title,
                author=poet,
                year=None,
                word_count=word_count,
                text=text,
                source_url=f"https://poetrydb.org/title/{requests.utils.quote(title)}",
                source_name="PoetryDB",
            )
            count += 1

        print(f"{count} poems")
        total += count

    print(f"\nDone. Total poems in DB: {count_by_type().get('poem', 0)}")


if __name__ == "__main__":
    ingest_poems()
