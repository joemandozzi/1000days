"""
Ingest high-quality early 20th century literary fiction and essays.

Run: python ingest/literary_additions.py
"""
import sys
import re
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import requests
from corpus.db import init_db, insert_work, count_by_type, get_conn

TXT_URL = "https://www.gutenberg.org/cache/epub/{id}/pg{id}.txt"
HEADERS_REQ = {"User-Agent": "bradbury-literary-ingest/1.0"}

# ---------------------------------------------------------------------------
# Collections to ingest
# Each entry:
#   id        — Gutenberg ID
#   author    — canonical author name
#   type      — 'story' or 'essay'
#   toc_end   — approx char position where TOC ends and content begins
#   case      — 'upper' (ALL-CAPS headers) | 'title' (Title Case headers)
#               | 'upper_after_roman' (essays titled without leading Roman numeral)
#   titles    — if set, only keep sections whose header matches one of these
#   skip      — headers to always skip
# ---------------------------------------------------------------------------
COLLECTIONS = [
    # ── STORIES ────────────────────────────────────────────────────────────
    {
        "id": 13555, "author": "Willa Cather", "type": "story",
        "toc_end": 800, "case": "title",
        "titles": [
            "Coming, Aphrodite!",
            "The Diamond Mine",
            "A Gold Slipper",
            "Scandal",
            "Paul's Case",
            "A Wagner Matinée",
            "The Sculptor's Funeral",
            '"A Death in the Desert"',
        ],
    },
    {
        "id": 346, "author": "Willa Cather", "type": "story",
        "toc_end": 460, "case": "title",
        "titles": [
            "On the Divide",
            "Eric Hermannson's Soul",
            "The Sculptor's Funeral",
            "A Wagner Matinee",
            "Paul's Case",
            "Flavia and Her Artists",
            "The Garden Lodge",
            "The Marriage of Phaedra",
            "The Professor's Commencement",
            "El Dorado: A Kansas Recessional",
        ],
    },
    {
        "id": 45524, "author": "Stephen Crane", "type": "story",
        "toc_end": 2400, "case": "upper",
        "titles": [
            "THE OPEN BOAT",
            "A MAN AND SOME OTHERS",
            "ONE DASH—HORSES",
            "THE BRIDE COMES TO YELLOW SKY",
            "THE WISE MEN",
            "DEATH AND THE CHILD",
            "THE FIVE WHITE MICE",
        ],
    },
    {
        "id": 68542, "author": "Theodore Dreiser", "type": "story",
        "toc_end": 1100, "case": "upper",
        "titles": [
            "FREE",
            "MCEWEN OF THE SHINING SLAVE MAKERS",
            "THE LOST PHŒBE",
            "THE SECOND CHOICE",
            "A STORY OF STORIES",
            "OLD ROGAUM AND HIS THERESA",
            "THE CRUISE OF THE \"IDLEWILD\"",
        ],
    },
    {
        "id": 306, "author": "Edith Wharton", "type": "story",
        "toc_end": 3000, "case": "upper",
        "skip": ["THE EARLY SHORT FICTION OF EDITH WHARTON"],
    },
    # ── ESSAYS ─────────────────────────────────────────────────────────────
    {
        "id": 67628, "author": "Randolph Bourne", "type": "essay",
        "toc_end": 1100, "case": "upper",
        "titles": [
            "YOUTH",
            "THE TWO GENERATIONS",
            "THE VIRTUES AND THE SEASONS OF LIFE",
            "THE LIFE OF IRONY",
            "THE EXCITEMENT OF FRIENDSHIP",
            "THE ADVENTURE OF LIFE",
            "SOME THOUGHTS ON RELIGION",
            "THE MYSTIC TURNED RADICAL",
            "SEEING, WE SEE NOT",
            "THE EXPERIMENTAL LIFE",
            "MON AMIE",
            "THE DODGING OF PRESSURES",
            "THE COLLEGE: AN INNER VIEW",
        ],
    },
    {
        "id": 2398, "author": "Walter Pater", "type": "essay",
        "toc_end": 50000, "case": "upper",
        "titles": [
            "PREFACE",
            "TWO EARLY FRENCH STORIES",
            "PICO DELLA MIRANDOLA",
            "SANDRO BOTTICELLI",
            "LUCA DELLA ROBBIA",
            "THE POETRY OF MICHELANGELO",
            "LEONARDO DA VINCI",
            "THE SCHOOL OF GIORGIONE",
            "JOACHIM DU BELLAY",
            "WINCKELMANN",
            "CONCLUSION",
        ],
    },
    {
        "id": 29220, "author": "Virginia Woolf", "type": "essay",
        "toc_end": 840, "case": "upper",
        "titles": [
            "A HAUNTED HOUSE",
            "A SOCIETY",
            "MONDAY OR TUESDAY",
            "AN UNWRITTEN NOVEL",
            "THE STRING QUARTET",
            "BLUE AND GREEN",
            "KEW GARDENS",
            "THE MARK ON THE WALL",
        ],
    },
    {
        "id": 31017, "author": "James Huneker", "type": "essay",
        "toc_end": 30000, "case": "upper",
        "skip": ["IVORY APES AND PEACOCKS", "PUBLISHED SEPTEMBER,", "CONTENTS",
                 "PAGE", "ALL RIGHTS RESERVED"],
    },
]


def fetch_text(gid: int) -> str:
    url = TXT_URL.format(id=gid)
    r = requests.get(url, headers=HEADERS_REQ, timeout=60)
    r.raise_for_status()
    try:
        return r.content.decode("utf-8")
    except UnicodeDecodeError:
        return r.content.decode("latin-1")


def strip_gutenberg(text: str) -> str:
    for m in ["*** START OF THE PROJECT GUTENBERG", "***START OF THE PROJECT GUTENBERG"]:
        idx = text.find(m)
        if idx != -1:
            text = text[text.find("\n", idx) + 1:]
            break
    for m in ["*** END OF THE PROJECT GUTENBERG", "***END OF THE PROJECT GUTENBERG",
              "End of the Project Gutenberg", "End of Project Gutenberg"]:
        idx = text.find(m)
        if idx != -1:
            text = text[:idx]
            break
    return text.strip()


def is_standalone(lines: list, i: int) -> bool:
    """True if line i is surrounded by blank lines."""
    return (0 < i < len(lines) - 1
            and not lines[i - 1].strip()
            and not lines[i + 1].strip())


def split_into_sections(text: str, col: dict):
    """
    Split text into (title, body) sections.
    Only looks at content after col['toc_end'] character position.
    """
    case    = col["case"]
    wanted  = {t.upper() for t in col.get("titles", [])} or None
    skipped = {s.upper() for s in col.get("skip", [])}

    lines      = text.split("\n")
    char_pos   = 0
    toc_end    = col["toc_end"]

    section_starts = []  # list of (title, char_pos_of_first_body_line)

    for i, line in enumerate(lines):
        line_start = char_pos
        char_pos  += len(line) + 1

        if line_start < toc_end:
            continue

        stripped = line.strip()
        if not stripped or len(stripped) < 3 or len(stripped) > 90:
            continue
        if not is_standalone(lines, i):
            continue

        # Strip TOC page numbers ("TITLE     9")
        cleaned = re.sub(r"\s{2,}\d+\s*$", "", stripped).strip()
        if not cleaned or cleaned.upper() in skipped:
            continue
        # Skip obvious non-titles
        if cleaned.startswith("[") or cleaned.startswith("_"):
            continue
        if re.match(r"^\*+$", cleaned):
            continue

        is_match = False
        if case == "upper" and cleaned == cleaned.upper() and cleaned[0].isalpha():
            is_match = True
        elif case == "title":
            # Title Case: first letter upper, has lower letters too
            if cleaned[0].isupper() and any(c.islower() for c in cleaned):
                is_match = True

        if not is_match:
            continue

        header_key = cleaned.upper()
        if wanted and header_key not in wanted:
            continue

        # char_pos now points to AFTER this line
        section_starts.append((cleaned, char_pos))

    # Build sections from start positions
    sections = []
    for idx, (title, body_start) in enumerate(section_starts):
        body_end = section_starts[idx + 1][1] if idx + 1 < len(section_starts) else len(text)
        body = text[body_start:body_end].strip()
        words = len(body.split())
        if 250 <= words <= 24000:
            sections.append((title, body, words))

    return sections


def already_exists(title: str, author: str) -> bool:
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        "SELECT id FROM works WHERE LOWER(title)=LOWER(?) AND LOWER(author)=LOWER(?)",
        (title, author),
    )
    row = c.fetchone()
    conn.close()
    return row is not None


def ingest_collection(col: dict) -> int:
    gid    = col["id"]
    author = col["author"]
    wtype  = col["type"]

    print(f"\n  Fetching PG#{gid} ({author})...")
    try:
        raw = strip_gutenberg(fetch_text(gid))
    except Exception as e:
        print(f"  ERROR: {e}")
        return 0

    sections = split_into_sections(raw, col)
    if not sections:
        print(f"  WARNING: no sections found")
        return 0

    added = 0
    for title, body, words in sections:
        # Normalise title to Title Case if it came in as ALL-CAPS
        display_title = title.title() if title == title.upper() else title
        # Fix common title-case oddities
        display_title = re.sub(r"\b(A|An|The|And|But|Or|In|Of|On|At|To|For)\b",
                                lambda m: m.group(0).lower(), display_title)
        display_title = display_title[0].upper() + display_title[1:]

        if already_exists(display_title, author):
            print(f"    skip (exists): {display_title}")
            continue

        insert_work(
            type=wtype,
            title=display_title,
            author=author,
            year=None,
            word_count=words,
            text=body,
            source_url=f"https://www.gutenberg.org/ebooks/{gid}",
            source_name="Project Gutenberg",
        )
        print(f"    ✓ {display_title} ({words:,} words)")
        added += 1

    return added


def rebalance_db():
    """Push over-represented genres to the back of the queue."""
    conn = get_conn()
    c = conn.cursor()

    fairy_tale_authors = [
        "Jacob Grimm", "A. N. Afanasyev", "Joseph Jacobs",
        "Frank Hamilton Cushing", "Beatrix Potter",
    ]
    for author in fairy_tale_authors:
        c.execute(
            "UPDATE works SET served=1 WHERE type='story' AND author=? AND served=0",
            (author,),
        )
        print(f"  Fairy tales marked served: {c.rowcount} by {author}")

    # Keep 80 Spectator/Rambler essays active, push the rest to served
    spectator_authors = (
        "'Joseph Addison','Richard Steele','Eustace Budgell',"
        "'John Byrom','John Hughes','Alexander Pope',"
        "'Thomas Tickell','Thomas Parnell','Steel','Henley'"
    )
    c.execute(
        f"""UPDATE works SET served=1
            WHERE type='essay'
              AND author IN ({spectator_authors})
              AND served=0
              AND id NOT IN (
                SELECT id FROM works
                WHERE type='essay'
                  AND author IN ({spectator_authors})
                  AND served=0
                ORDER BY RANDOM() LIMIT 80
              )"""
    )
    print(f"  Excess Spectator essays pushed to served: {c.rowcount}")

    c.execute(
        """UPDATE works SET served=1
           WHERE type='essay' AND author='Samuel Johnson' AND served=0
             AND id NOT IN (
               SELECT id FROM works WHERE type='essay' AND author='Samuel Johnson'
               AND served=0 ORDER BY RANDOM() LIMIT 50
             )"""
    )
    print(f"  Excess Rambler essays pushed to served: {c.rowcount}")

    c.execute(
        """UPDATE works SET served=1
           WHERE type='essay' AND author='Michel de Montaigne' AND served=0
             AND id NOT IN (
               SELECT id FROM works WHERE type='essay' AND author='Michel de Montaigne'
               AND served=0 ORDER BY RANDOM() LIMIT 50
             )"""
    )
    print(f"  Excess Montaigne essays pushed to served: {c.rowcount}")

    conn.commit()
    conn.close()


def main():
    init_db()
    total_stories = 0
    total_essays  = 0

    for col in COLLECTIONS:
        n = ingest_collection(col)
        if col["type"] == "story":
            total_stories += n
        else:
            total_essays += n

    print("\n=== REBALANCING ===")
    rebalance_db()

    counts = count_by_type()
    print(f"\nDone. Added {total_stories} stories, {total_essays} essays.")
    print(f"DB totals — stories: {counts.get('story')}, "
          f"essays: {counts.get('essay')}, poems: {counts.get('poem')}")


if __name__ == "__main__":
    main()
