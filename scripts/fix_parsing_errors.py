"""
Fix 28 confirmed parsing errors found in the deep Gutenberg content audit.

Approach:
  - DELETE: truncated/unfixable records (5 records)
  - TRUNCATE TEXT: strip bleed-through content at known markers (19 records)
  - STRIP PREFIX: remove Gutenberg production credits from story start (1 record)
  - TRUNCATE MERGE: cut merged works at the second essay's title (3 records)
"""
import re
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from corpus.db import get_conn

conn = get_conn()
c = conn.cursor()

fixed = 0
deleted = 0

# ── 1. DELETE truncated / unfixable records ────────────────────────────────────

delete_ids = [
    4164,  # Lamb "Newspapers Thirty-Five Years Ago" — ends mid-sentence
    4171,  # Lamb "Popular Fallacies" — truncated + wrong split
    4172,  # Lamb "He Is No Gentleman" — wrong title, fragment of Popular Fallacies
    4173,  # Lamb "Translation" — wrong title, fragment of Popular Fallacies
    5522,  # Mencken "Miscellaneous Notes" — truncated mid-sentence
]
c.execute(f"DELETE FROM works WHERE id IN ({','.join(str(i) for i in delete_ids)})")
deleted += c.rowcount
print(f"Deleted {c.rowcount} truncated/unfixable records")


# ── 2. STRIP PREFIX — Daisy Miller (1330) ─────────────────────────────────────

row = c.execute("SELECT text FROM works WHERE id=1330").fetchone()
if row:
    text = row[0]
    # Find start of actual prose ("At the little town of Vevey")
    marker = "At the little town of Vevey"
    idx = text.find(marker)
    if idx != -1:
        new_text = text[idx:]
        c.execute("UPDATE works SET text=?, word_count=? WHERE id=1330",
                  (new_text, len(new_text.split())))
        fixed += 1
        print(f"Fixed 1330 (Daisy Miller): stripped {idx}-char prefix")


# ── 3. TRUNCATE TEXT at bleed markers ─────────────────────────────────────────

def truncate_at(work_id, *markers):
    """Strip everything from the first matching marker onward."""
    row = c.execute("SELECT title, text FROM works WHERE id=?", (work_id,)).fetchone()
    if not row:
        return False
    title, text = row
    for marker in markers:
        idx = text.find(marker)
        if idx != -1:
            new_text = text[:idx].rstrip()
            c.execute("UPDATE works SET text=?, word_count=? WHERE id=?",
                      (new_text, len(new_text.split()), work_id))
            print(f"  Fixed {work_id} ({title[:50]}): stripped at {idx:,}/{len(text):,} chars")
            return True
    print(f"  WARNING: no marker found for {work_id} ({title[:50]})")
    return False


# Bacon 4022 — strip glossary after essay ends
truncate_at(4022,
    "\n\nUnder foot",   # start of glossary
    "Under foot:",
)

# Montaigne (13) — strip volume separator pages
montaigne_ids = [4034, 4043, 4046, 4047, 4057, 4065, 4075, 4080, 4089, 4102, 4108, 4111, 4114, 4117]
print(f"\nFixing {len(montaigne_ids)} Montaigne bleed-through records...")
for wid in montaigne_ids:
    truncate_at(wid,
        "\n\nESSAYS OF MICHEL DE MONTAIGNE",
        "\n\nESSAYS OF MONTAIGNE",
        "\n\nBOOK THE SECOND",
        "\n\nBOOK THE THIRD",
        "\n\nTRANSLATED BY CHARLES COTTON",
    )

# Spectator (2) — strip "END OF VOLUME" and everything after
print("\nFixing 2 Spectator bleed-through records...")
truncate_at(4350, "\n\nEND OF VOLUME I", "\n\nTHE SPECTATOR\n\nVOL. II")
truncate_at(4525, "\n\nEND OF VOLUME II", "\n\nTHE SPECTATOR\n\nVOL. III")

# Mencken (3) — strip INDEX sections
print("\nFixing 3 Mencken bleed-through records...")
truncate_at(5504, "\n\n    INDEX\n\n")
truncate_at(5485, "\n\n    INDEX\n\n")
truncate_at(5636, "\n\n                                 INDEX\n\n", "\n\nTHE END\n\n")


# ── 4. TRUNCATE MERGE — Lamb multi-essay records ──────────────────────────────

print("\nFixing 3 merged Lamb records...")
truncate_at(4125, "\n\nMRS. BATTLE'S OPINIONS ON WHIST")
truncate_at(4160, "\n\nBARBARA S----")
truncate_at(4170, "\n\nOLD CHINA")


# ── 5. Verify and commit ───────────────────────────────────────────────────────

conn.commit()
conn.close()

total_fixed = fixed + (len(montaigne_ids) + 1 + 2 + 3 + 3)  # rough count
print(f"\nDone. Deleted: {deleted}  Text fixes applied: see above")

# Quick sanity check
from corpus.db import get_conn
conn2 = get_conn()
counts = conn2.execute("SELECT type, COUNT(*) FROM works WHERE served=0 GROUP BY type").fetchall()
print("\nUnserved counts after fix:")
for row in counts:
    print(f"  {row[0]}: {row[1]:,}")
conn2.close()
