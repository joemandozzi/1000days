"""
Ingest essays — Phase 1 seed from Harvard Classics vols. 27 & 28.

These two Gutenberg plain-text files are pre-segmented anthologies. Each essay
is separated by a clear header line (the title in ALL CAPS or with a rule).
We parse each volume's table of contents to find titles and authors, then
locate the matching text blocks.

Run: python ingest/essays.py
"""
import sys
import re
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import requests
from corpus.db import init_db, insert_work, count_by_type

# Harvard Classics — Gutenberg plain-text URLs.
# Vol 27: English Essays: Sidney to Macaulay
# Vol 28: Essays: English and American
VOLUMES = [
    {
        "gutenberg_id": 5226,
        "url": "https://www.gutenberg.org/cache/epub/5226/pg5226.txt",
        "volume": "Harvard Classics Vol. 27",
    },
    {
        "gutenberg_id": 5227,
        "url": "https://www.gutenberg.org/cache/epub/5227/pg5227.txt",
        "volume": "Harvard Classics Vol. 28",
    },
]

# Hand-curated list of essays known to be in these volumes.
# Format: (title_fragment, author)
# title_fragment is a substring of the essay's actual header — enough to find it.
SEED_ESSAYS = [
    # Vol 27 — Sidney to Macaulay
    ("Of Studies",             "Francis Bacon"),
    ("Of Truth",               "Francis Bacon"),
    ("Of Death",               "Francis Bacon"),
    ("Of Friendship",          "Francis Bacon"),
    ("Of Marriage and Single Life", "Francis Bacon"),
    ("Of Great Place",         "Francis Bacon"),
    ("Of Travel",              "Francis Bacon"),
    ("Of Gardens",             "Francis Bacon"),
    ("Of Adversity",           "Francis Bacon"),
    # Vol 28 — English and American
    ("Self-Reliance",          "Ralph Waldo Emerson"),
    ("Nature",                 "Ralph Waldo Emerson"),
    ("The American Scholar",   "Ralph Waldo Emerson"),
    ("Compensation",           "Ralph Waldo Emerson"),
    ("Circles",                "Ralph Waldo Emerson"),
    ("Thoreau",                "Ralph Waldo Emerson"),
    ("Walking",                "Henry David Thoreau"),
    ("Civil Disobedience",     "Henry David Thoreau"),
    ("On the Duty of Civil Disobedience", "Henry David Thoreau"),
]

# Approximate word-count cutoff; essays over this are trimmed for display.
MAX_WORDS = 8000


def fetch_text(url: str) -> str:
    resp = requests.get(url, timeout=60)
    resp.raise_for_status()
    # Gutenberg files are Latin-1 or UTF-8; try both.
    try:
        return resp.content.decode("utf-8")
    except UnicodeDecodeError:
        return resp.content.decode("latin-1")


def clean_gutenberg_text(text: str) -> str:
    """Strip Gutenberg header/footer boilerplate."""
    start_markers = ["*** START OF THE PROJECT GUTENBERG", "***START OF THE PROJECT GUTENBERG"]
    end_markers   = ["*** END OF THE PROJECT GUTENBERG",   "***END OF THE PROJECT GUTENBERG"]
    for m in start_markers:
        idx = text.find(m)
        if idx != -1:
            text = text[text.find("\n", idx) + 1:]
            break
    for m in end_markers:
        idx = text.find(m)
        if idx != -1:
            text = text[:idx]
            break
    return text.strip()


def find_essay_text(full_text: str, title_fragment: str) -> str | None:
    """
    Locate the block of text for an essay by searching for the title fragment.
    Returns cleaned text or None if not found.
    """
    # Case-insensitive search for the title.
    pattern = re.compile(re.escape(title_fragment), re.IGNORECASE)
    match = pattern.search(full_text)
    if not match:
        return None

    # Walk forward to find the start of the actual prose (skip header lines).
    start = full_text.find("\n", match.end()) + 1
    # Find the next all-caps heading or a line of asterisks/dashes as the end.
    end_pattern = re.compile(r"\n\n[A-Z][A-Z\s,;:\'\"]{10,}\n", re.MULTILINE)
    end_match = end_pattern.search(full_text, start + 200)
    if end_match:
        block = full_text[start:end_match.start()]
    else:
        # Fall back: take up to MAX_WORDS worth of characters.
        block = full_text[start:start + MAX_WORDS * 7]

    # Normalize whitespace.
    block = re.sub(r"\r\n", "\n", block)
    block = re.sub(r"\n{3,}", "\n\n", block)
    return block.strip()


def ingest_essays():
    init_db()
    total = 0

    for vol in VOLUMES:
        print(f"\nFetching {vol['volume']}...")
        try:
            raw = fetch_text(vol["url"])
        except Exception as e:
            print(f"  ERROR fetching {vol['url']}: {e}")
            continue

        text = clean_gutenberg_text(raw)

        for title_frag, author in SEED_ESSAYS:
            essay_text = find_essay_text(text, title_frag)
            if not essay_text:
                # Try the other volume.
                continue

            word_count = len(essay_text.split())
            if word_count < 50:
                continue  # found a header but no real text

            work_id = insert_work(
                type="essay",
                title=title_frag,
                author=author,
                year=None,
                word_count=word_count,
                text=essay_text,
                source_url=f"https://www.gutenberg.org/ebooks/{vol['gutenberg_id']}",
                source_name=vol["volume"],
            )
            print(f"  ✓ {title_frag} — {author} ({word_count:,} words)")
            total += 1

    print(f"\nDone. Total essays in DB: {count_by_type().get('essay', 0)}")


if __name__ == "__main__":
    ingest_essays()
