"""
build.py — entry point for the static site generator.

Usage:
  python build.py              # build today's page
  python build.py 2026-06-10   # build a specific date
  python build.py --all        # build every date from launch to today

Output goes to site/. Open site/index.html in a browser.
"""
import sys
import shutil
from datetime import date, datetime, timedelta
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from corpus.db import init_db, count_by_type
from picker import pick_for_date, reading_time_minutes
from external_picks import get_external_picks


# ── paths ──────────────────────────────────────────────────────────────────
ROOT        = Path(__file__).parent
TEMPLATES   = ROOT / "templates"
STATIC      = ROOT / "static"
SITE        = ROOT / "site"
LAUNCH_DATE = date(2026, 6, 10)


# ── Jinja2 custom filters ──────────────────────────────────────────────────
def nl2br(text):
    """Convert newlines to <br> tags (used for poem text)."""
    from markupsafe import Markup, escape
    return Markup(escape(text).replace("\n", Markup("<br>\n")))

def wordcount_label(n):
    """'~400 words · ~2 min read'"""
    n = int(n or 0)
    if n == 0:
        return ""
    mins = max(1, round(n / 200))  # ~200 wpm for literary reading
    return f"~{n:,} words · ~{mins} min read"


# ── build ──────────────────────────────────────────────────────────────────
def _setup(today: date) -> tuple:
    """One-time setup: init DB, copy static assets, create Jinja env. Returns (env, today_display)."""
    init_db()

    counts = count_by_type()
    if sum(counts.values()) == 0:
        print("Database is empty. Run the ingest scripts first.")
        print("  python ingest/poems.py")
        print("  python ingest/essays.py")
        print("  python ingest/stories.py")

    SITE.mkdir(exist_ok=True)

    dest_static = SITE / "static"
    if dest_static.exists():
        shutil.rmtree(dest_static)
    shutil.copytree(STATIC, dest_static)

    env = Environment(loader=FileSystemLoader(str(TEMPLATES)), autoescape=True)
    env.filters["nl2br"] = nl2br
    env.filters["wordcount_label"] = wordcount_label

    return env, today.strftime("%B %-d, %Y")


def _render_date(env, target_date: date, is_today: bool = False):
    """Render one date's page. Always writes the dated permalink; also writes root if is_today."""
    triad        = pick_for_date(target_date)
    date_display = target_date.strftime("%B %-d, %Y")
    read_time    = reading_time_minutes(triad)
    ext          = get_external_picks(target_date)

    shared_ctx = dict(
        date_iso=target_date.isoformat(),
        date_display=date_display,
        read_time=read_time,
        story=triad.get("story"),
        poem=triad.get("poem"),
        essay=triad.get("essay"),
        ext_story=ext.get("story"),
        ext_essay=ext.get("essay"),
    )

    day_tmpl = env.get_template("day.html")

    # Always write the dated permalink.
    dated_dir = SITE / target_date.isoformat()
    dated_dir.mkdir(exist_ok=True)
    (dated_dir / "index.html").write_text(
        day_tmpl.render(root="../", **shared_ctx), encoding="utf-8"
    )

    # Today's date also becomes the root index and about page.
    if is_today:
        (SITE / "index.html").write_text(
            day_tmpl.render(root="", **shared_ctx), encoding="utf-8"
        )
        about_html = env.get_template("about.html").render(root="", date_display=date_display)
        (SITE / "about.html").write_text(about_html, encoding="utf-8")

        print(f"Built site/ for {date_display}")
        print(f"  story      : {triad['story']['title'] if triad.get('story') else 'none'}")
        print(f"  poem       : {triad['poem']['title']  if triad.get('poem')  else 'none'}")
        print(f"  essay      : {triad['essay']['title'] if triad.get('essay') else 'none'}")
        print(f"  ext story  : {ext['story']['title']   if ext.get('story')   else 'none'}")
        print(f"  ext essay  : {ext['essay']['title']   if ext.get('essay')   else 'none'}")
        print(f"Open: site/index.html")


def build(target_date: date):
    """Build a single date (also writes root index/about)."""
    env, _ = _setup(target_date)
    _render_date(env, target_date, is_today=True)


def build_all():
    """Build every date from LAUNCH_DATE to today. Permalinks are permanent."""
    today = date.today()
    env, _ = _setup(today)
    current = LAUNCH_DATE
    count = 0
    while current <= today:
        _render_date(env, current, is_today=(current == today))
        current += timedelta(days=1)
        count += 1
    print(f"Built {count} dated pages (launch → today).")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--all":
        build_all()
    elif len(sys.argv) > 1:
        target = datetime.strptime(sys.argv[1], "%Y-%m-%d").date()
        build(target)
    else:
        build(date.today())
