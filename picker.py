"""
Date-seeded daily picker.

Given a date, deterministically selects one story, one poem, and one essay.
The seed is the ISO date string (e.g. "2026-06-10"), so:
- Everyone sees the same triad on the same day.
- You can regenerate any past day by passing that date.
- Works are drawn from the unserved pool first; once all are served the pool resets.
"""
import random
from datetime import date
from corpus.db import get_works_by_type, mark_served


def pick_for_date(target_date: date | None = None) -> dict:
    """
    Returns {'story': Row, 'poem': Row, 'essay': Row} for the given date.
    Defaults to today if no date is supplied.
    """
    if target_date is None:
        target_date = date.today()

    seed = target_date.isoformat()  # e.g. "2026-06-10"
    rng = random.Random(seed)

    result = {}
    for work_type in ("story", "poem", "essay"):
        works = get_works_by_type(work_type)
        if not works:
            result[work_type] = None
            continue

        # Prefer unserved works; fall back to the full pool if all are served.
        unserved = [w for w in works if not w["served"]]
        pool = unserved if unserved else list(works)

        # Bias toward shorter works: weight inversely by word count.
        # Works with no word_count get a neutral weight of 500.
        def weight(w):
            wc = w["word_count"] or 500
            return 1.0 / max(wc, 1)

        weights = [weight(w) for w in pool]
        chosen = rng.choices(pool, weights=weights, k=1)[0]
        mark_served(chosen["id"])
        result[work_type] = chosen

    return result
