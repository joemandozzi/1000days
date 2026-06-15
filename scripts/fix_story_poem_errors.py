"""
Fix confirmed errors from the story and poem content audits.

Stories:
  - DELETE 1 wrong-content story (Ransom of Red Chief contains Gift of the Magi)
  - DELETE 12 truncated stories (SE parser drops non-<p> final elements)
  - FIX 9 wrong-start stories (strip TOC/metadata prefix from Gutenberg files)

Poems:
  - DELETE 20 dramatic works (Byron/Shelley plays misclassified as poems)
  - DELETE 2 truncated poems (Song of Myself partial, Evangeline partial)
  - FIX 1 editorial artifact (Sensitive Plant "CANCELLED PASSAGE" appended)
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from corpus.db import get_conn

conn = get_conn()
c = conn.cursor()

# ── STORY DELETES ──────────────────────────────────────────────────────────────

story_deletes = [
    1324,  # "Ransom of Red Chief" — actually contains "Gift of the Magi"
    # Truncated mid-sentence (SE parser dropped non-<p> final elements):
    1427,  # Kuprin "Allez!" — ends "she cried out, as if in the circus:"
    1432,  # Kuprin "Cain" — ends mid-sentence comma
    1580,  # Chekhov "Bad Weather" — ends "as he dozed off, he said to himself:"
    1978,  # Maupassant "A Coward" — ends "made a great red mark beneath these four words:"
    2031,  # Maupassant "Caresses" — ends "after one o'clock Mass, by"
    2101,  # Maupassant "Mouche" — ends "And we answered together:"
    2764,  # Andreyev "A Dilemma" — ends "upon him, he repeated:"
    2824,  # M.R. James "An Episode of Cathedral History" — ends "merely of the three words—"
    2915,  # O. Henry "A Sacrifice Hit" — ends "scribbled with a piece of charcoal:"
    2995,  # O. Henry "In Mezzotint" — ends "it now read:"
    3173,  # O. Henry "The Rose of Dixie" — ends mid-article-header
    3220,  # O. Henry "While the Auto Waits" — ends "said two words to the chauffeur:"
]
c.execute(f"DELETE FROM works WHERE id IN ({','.join(str(i) for i in story_deletes)})")
print(f"Deleted {c.rowcount} stories (1 wrong-content + 12 truncated)")

# ── POEM DELETES ───────────────────────────────────────────────────────────────

poem_deletes = [
    # Byron/Shelley dramatic plays misclassified as poems:
    513,   # Shelley: Scenes From the Magico Prodigioso
    514,   # Shelley: Scenes From the Faust of Goethe
    567,   # Shelley: Prometheus Unbound (4-act lyrical drama)
    568,   # Shelley: The Cenci (5-act tragedy)
    571,   # Shelley: Oedipus Tyrannus / Swellfoot the Tyrant
    574,   # Shelley: Hellas: A Lyrical Drama
    575,   # Shelley: Fragments of an Unfinished Drama
    576,   # Shelley: Charles the First
    618,   # Shelley: Scene From 'Tasso'
    753,   # Shelley: The Cyclops (translated Euripides)
    1244,  # Byron: Manfred: A Dramatic Poem
    1250,  # Byron: Marino Faliero (5-act historical tragedy)
    1258,  # Byron: The Blues: A Literary Eclogue
    1259,  # Byron: Sardanapalus (full play)
    1260,  # Byron: The Two Foscari (full play)
    1261,  # Byron: Cain: A Mystery (full play)
    1262,  # Byron: Heaven and Earth (full play)
    1263,  # Byron: Werner; or, the Inheritance (5-act play)
    1264,  # Byron: Werner: First Draft
    1265,  # Byron: The Deformed Transformed (full play)
    # Truncated poems:
    398,   # "Walt Whitman." — actually Song of Myself sections 1-37 only, ends mid-sentence
    959,   # Longfellow "Evangeline" — Part One only, Part Two missing entirely
]
c.execute(f"DELETE FROM works WHERE id IN ({','.join(str(i) for i in poem_deletes)})")
print(f"Deleted {c.rowcount} poems (20 misclassified plays + 2 truncated)")

# ── STORY TEXT FIXES — strip TOC/metadata prefixes ────────────────────────────

def fix_start(work_id, prose_marker, include_marker=True):
    """Strip everything before prose_marker. Optionally include the marker itself."""
    row = c.execute("SELECT title, text FROM works WHERE id=?", (work_id,)).fetchone()
    if not row:
        print(f"  WARNING: {work_id} not found")
        return
    title, text = row
    idx = text.find(prose_marker)
    if idx == -1:
        print(f"  WARNING: marker not found in {work_id} ({title})")
        return
    new_text = text[idx:] if include_marker else text[idx + len(prose_marker):]
    new_text = new_text.strip()
    c.execute("UPDATE works SET text=?, word_count=? WHERE id=?",
              (new_text, len(new_text.split()), work_id))
    print(f"  Fixed {work_id} ({title[:50]}): stripped {idx}-char prefix")

print("\nFixing wrong-start stories...")
# Strip TOC and subtitle cruft — start each at first real prose sentence
fix_start(1327, "Buck did not read the newspapers")          # Call of the Wild
fix_start(1331, "Mr. Utterson the lawyer was a man")        # Jekyll & Hyde
fix_start(1332, "I am glad you came, Clarke")               # The Great God Pan
fix_start(1333, "I HAVE endeavoured in this Ghostly")       # Christmas Carol (keep Dickens's own preface)
fix_start(1334, "The Time Traveller")                       # The Time Machine
fix_start(1335, "When I was a student")                     # Island of Doctor Moreau
fix_start(1311, "A man stood upon a railroad bridge")       # Owl Creek Bridge
fix_start(1320, "The thousand injuries of Fortunato")       # Cask of Amontillado
fix_start(1325, "Without, the night was cold and wet")      # The Monkey's Paw

# ── POEM TEXT FIX — strip editorial appendage from The Sensitive Plant ────────

row = c.execute("SELECT text FROM works WHERE id=507").fetchone()
if row:
    text = row[0]
    marker = "\n\nCANCELLED PASSAGE."
    idx = text.find(marker)
    if idx != -1:
        new_text = text[:idx].rstrip()
        c.execute("UPDATE works SET text=?, word_count=? WHERE id=507",
                  (new_text, len(new_text.split())))
        print(f"\nFixed ID 507 (The Sensitive Plant): stripped {len(text)-idx}-char editorial appendage")
    else:
        print("\nWARNING: CANCELLED PASSAGE marker not found in ID 507")

# ── Summary ────────────────────────────────────────────────────────────────────

conn.commit()

counts = conn.execute(
    "SELECT type, COUNT(*) FROM works WHERE served=0 GROUP BY type"
).fetchall()
print("\nUnserved counts after all fixes:")
for row in counts:
    print(f"  {row[0]}: {row[1]:,}")

conn.close()
