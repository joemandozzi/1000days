"""
Ingest poetry collections from Standard Ebooks.

Parses XHTML files for <article epub:type="z3998:poem"> elements.
Run: python ingest/se_poems.py
"""
import sys, re
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import requests
from bs4 import BeautifulSoup
from corpus.db import init_db, insert_work, count_by_type

GITHUB_RAW = "https://raw.githubusercontent.com/standardebooks"
GITHUB_API = "https://api.github.com/repos/standardebooks"

import os
HEADERS = {"Authorization": f"token {os.environ['GITHUB_TOKEN']}"} if os.environ.get("GITHUB_TOKEN") else {}

SKIP_FILES = {
    "colophon.xhtml", "titlepage.xhtml", "imprint.xhtml", "halftitlepage.xhtml",
    "uncopyright.xhtml", "dedication.xhtml", "epigraph.xhtml", "foreword.xhtml",
    "preface.xhtml", "introduction.xhtml", "appendix.xhtml", "endnotes.xhtml",
    "loi.xhtml", "acknowledgments.xhtml",
}

POETRY_REPOS = [
    ("robert-frost_north-of-boston",             "Robert Frost"),
    ("robert-frost_new-hampshire",               "Robert Frost"),
    ("edgar-lee-masters_spoon-river-anthology",  "Edgar Lee Masters"),
    ("edward-thomas_poetry",                     "Edward Thomas"),
    ("wilfred-owen_poetry",                      "Wilfred Owen"),
    ("william-carlos-williams_poetry",           "William Carlos Williams"),
]


def get_text_files(repo: str) -> list[str]:
    resp = requests.get(f"{GITHUB_API}/{repo}/contents/src/epub/text", headers=HEADERS, timeout=15)
    resp.raise_for_status()
    return [f["name"] for f in resp.json() if f["name"].endswith(".xhtml") and f["name"] not in SKIP_FILES]


def fetch_xhtml(repo: str, filename: str) -> str:
    url = f"{GITHUB_RAW}/{repo}/master/src/epub/text/{filename}"
    resp = requests.get(url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    return resp.text


def extract_poems(xhtml: str) -> list[tuple[str, str]]:
    """Return list of (title, text) tuples from a poetry XHTML file."""
    soup = BeautifulSoup(xhtml, "html.parser")
    results = []

    for article in soup.find_all("article"):
        etype = article.get("epub:type", "")
        if "poem" not in etype and "z3998:poem" not in etype:
            continue

        # Title: first h2 or h3
        title_tag = article.find(["h2", "h3"])
        title = title_tag.get_text(" ", strip=True) if title_tag else ""
        if not title:
            continue

        # Remove title from text extraction
        if title_tag:
            title_tag.decompose()

        # Extract verse lines — preserve stanza breaks as blank lines
        lines = []
        for stanza in article.find_all(["p", "div"]):
            stanza_lines = []
            for elem in stanza.descendants:
                if isinstance(elem, str):
                    t = elem.strip()
                    if t:
                        stanza_lines.append(t)
                elif hasattr(elem, "name") and elem.name == "br":
                    stanza_lines.append("")
            if stanza_lines:
                lines.extend(stanza_lines)
                lines.append("")  # stanza break

        text = "\n".join(lines).strip()
        if text:
            results.append((title, text))

    return results


def ingest_repo(repo: str, author: str):
    print(f"\n  {author} ({repo})")
    files = get_text_files(repo)
    count = 0
    for filename in files:
        xhtml = fetch_xhtml(repo, filename)
        poems = extract_poems(xhtml)
        for title, text in poems:
            word_count = len(text.split())
            if word_count < 5:
                continue
            insert_work(
                type="poem",
                title=title,
                author=author,
                year=None,
                word_count=word_count,
                text=text,
                source_url=f"https://standardebooks.org/ebooks/{repo}",
                source_name="Standard Ebooks",
            )
            count += 1
    print(f"    {count} poems")
    return count


def main():
    init_db()
    total = 0
    for repo, author in POETRY_REPOS:
        total += ingest_repo(repo, author)
    print(f"\nDone. Total poems in DB: {count_by_type().get('poem', 0)}")


if __name__ == "__main__":
    main()
