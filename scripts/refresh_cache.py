"""
Refresh the local cache files used by external_picks.py.

  python scripts/refresh_cache.py            # refresh both
  python scripts/refresh_cache.py --el       # Electric Literature only
  python scripts/refresh_cache.py --nyt      # NYT Magazine only (needs NYT_API_KEY)

Cache files written to cache/:
  el_stories.json   — Electric Literature Recommended Reading + Lit Mags posts
  nyt_essays.json   — ~30 NYT Magazine articles per year, 1975-2024
"""
import argparse
import html
import json
import os
import random
import re
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

ROOT      = Path(__file__).parent.parent
CACHE_DIR = ROOT / "cache"

EL_CATEGORIES  = [63, 5557]   # Recommended Reading, Lit Mags
EL_API         = "https://electricliterature.com/wp-json/wp/v2/posts"
NYT_ARCHIVE    = "https://api.nytimes.com/svc/archive/v1/{year}/{month}.json"
NYT_YEAR_RANGE      = (1995, 2024)  # pre-1995 has sparse/unreliable magazine tagging
NYT_TARGET_PER_YEAR = 30           # articles to keep per year
NYT_MONTHS_PER_YEAR = [3, 7, 11]   # March, July, November — spread through the year
NYT_DELAY           = 12.0         # NYT rate limit: 10 req/min, 12s to be safe
NYT_RETRY_DELAYS    = [30, 60]     # backoff waits (seconds) on 429 before giving up


# ── helpers ────────────────────────────────────────────────────────────────

def _strip_html(text):
    return html.unescape(re.sub(r"<[^>]+>", "", text or "")).strip()

def _truncate(text, max_chars=320):
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rsplit(" ", 1)[0].rstrip(".,;:") + "…"

def _author_from_url(url):
    """Extract author from EL URL pattern: /story-title-by-author-name/"""
    m = re.search(r"-by-([\w-]+)/?$", url)
    if not m:
        return ""
    slug = m.group(1)
    return " ".join(w.capitalize() for w in slug.split("-"))

def _fetch_json(url, headers=None, delay=0.3, retry_delays=None):
    req = urllib.request.Request(url, headers=headers or {})
    attempts = [0] + (retry_delays or [])
    for wait in attempts:
        if wait:
            print(f"    rate limited — retrying in {wait}s…")
            time.sleep(wait)
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read())
            time.sleep(delay)
            return data
        except urllib.error.HTTPError as e:
            if e.code == 429 and wait != attempts[-1]:
                continue
            raise


# ── Electric Literature ─────────────────────────────────────────────────────

def refresh_el():
    print("Fetching Electric Literature posts…")
    seen = set()
    posts = []

    for cat_id in EL_CATEGORIES:
        page = 1
        while True:
            url = f"{EL_API}?per_page=100&categories={cat_id}&page={page}"
            try:
                batch = _fetch_json(url, headers={"User-Agent": "Bradbury/1.0"})
            except urllib.error.HTTPError as e:
                if e.code == 400:
                    break   # past last page
                raise
            except Exception as e:
                print(f"  Error page {page}: {e}")
                break

            if not batch:
                break

            for p in batch:
                link = p.get("link", "")
                if link in seen:
                    continue
                seen.add(link)

                title   = _strip_html(p.get("title", {}).get("rendered", ""))
                excerpt = _truncate(_strip_html(p.get("excerpt", {}).get("rendered", "")))
                author  = _author_from_url(link)

                if not title or not link:
                    continue

                posts.append({
                    "title":       title,
                    "author":      author,
                    "excerpt":     excerpt,
                    "url":         link,
                    "date":        p.get("date", "")[:10],
                    "source_name": "Electric Literature",
                })

            print(f"  cat {cat_id} page {page}: +{len(batch)} posts (total {len(posts)})")
            page += 1

    out = CACHE_DIR / "el_stories.json"
    out.write_text(json.dumps(posts, indent=2, ensure_ascii=False))
    print(f"Saved {len(posts)} EL posts → {out}")
    return posts


# ── NYT Magazine ────────────────────────────────────────────────────────────

_MAG_DESKS = {"magazine", "mag", "magazine desk"}

def _is_magazine(doc):
    desk = (doc.get("news_desk") or "").lower()
    url  = doc.get("web_url", "")
    return desk in _MAG_DESKS or "/magazine/" in url

def _is_readable(doc):
    bad = {"slideshow", "interactive feature", "video"}
    return (doc.get("type_of_material") or "").lower() not in bad

def _parse_nyt_doc(d):
    headline = (d.get("headline") or {}).get("main", "").strip()
    abstract = _truncate((d.get("abstract") or d.get("snippet") or "").strip())
    byline   = re.sub(
        r"^By\s+", "", (d.get("byline") or {}).get("original") or "", flags=re.I
    ).strip()
    web_url  = d.get("web_url", "")
    if not headline or not web_url:
        return None
    return {
        "title":       headline,
        "author":      byline,
        "excerpt":     abstract,
        "url":         web_url,
        "date":        (d.get("pub_date") or "")[:10],
        "source_name": "NYT Magazine",
    }


def refresh_nyt(api_key, start_year=None):
    # Load existing cache so we can append rather than overwrite
    out = CACHE_DIR / "nyt_essays.json"
    existing = json.loads(out.read_text()) if out.exists() else []
    existing_years = {a["date"][:4] for a in existing if a.get("date")}

    year_start = start_year or NYT_YEAR_RANGE[0]
    years = list(range(year_start, NYT_YEAR_RANGE[1] + 1))
    total_calls = len(years) * len(NYT_MONTHS_PER_YEAR)
    print(f"Fetching NYT Magazine articles — {len(years)} years × {len(NYT_MONTHS_PER_YEAR)} months = {total_calls} API calls (~{total_calls * NYT_DELAY / 60:.0f} min)…")

    rng      = random.Random(42)
    articles = list(existing)
    call_num = 0
    print(f"Resuming from {year_start} — {len(existing)} articles already cached")

    for year in years:
        year_pool = []

        for month in NYT_MONTHS_PER_YEAR:
            call_num += 1
            url = NYT_ARCHIVE.format(year=year, month=month) + f"?api-key={api_key}"
            try:
                data = _fetch_json(url, delay=NYT_DELAY, retry_delays=NYT_RETRY_DELAYS)
            except Exception as e:
                print(f"  [{call_num}/{total_calls}] {year}/{month:02d} error: {e}")
                continue

            docs = data.get("response", {}).get("docs", [])
            mag  = [d for d in docs if _is_magazine(d) and _is_readable(d)]
            year_pool.extend(mag)

        # Sample up to NYT_TARGET_PER_YEAR from the combined months
        sample = rng.sample(year_pool, min(NYT_TARGET_PER_YEAR, len(year_pool)))
        parsed = [p for d in sample if (p := _parse_nyt_doc(d))]
        articles.extend(parsed)
        print(f"  {year}: {len(year_pool)} pool → kept {len(parsed)} (running total: {len(articles)})")

    out = CACHE_DIR / "nyt_essays.json"
    out.write_text(json.dumps(articles, indent=2, ensure_ascii=False))
    print(f"Saved {len(articles)} NYT Magazine articles → {out}")
    return articles


# ── main ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--el",         action="store_true", help="Refresh Electric Literature only")
    parser.add_argument("--nyt",        action="store_true", help="Refresh NYT only")
    parser.add_argument("--start-year", type=int, default=None, help="NYT: start from this year (appends to existing cache)")
    args = parser.parse_args()

    do_el  = args.el  or not (args.el or args.nyt)
    do_nyt = args.nyt or not (args.el or args.nyt)

    if do_el:
        refresh_el()

    if do_nyt:
        api_key = os.environ.get("NYT_API_KEY")
        if not api_key:
            print("NYT_API_KEY not set — skipping NYT refresh")
        else:
            refresh_nyt(api_key, start_year=args.start_year)

    print("Done.")
