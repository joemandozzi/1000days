"""
SQLite helpers: schema creation, inserting works, querying for the picker.
All database access goes through this file so the schema lives in one place.
"""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "bradbury.db"


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # lets you access columns by name
    return conn


def init_db():
    """Create the works table if it doesn't exist yet."""
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS works (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                type        TEXT NOT NULL CHECK(type IN ('story', 'poem', 'essay')),
                title       TEXT NOT NULL,
                author      TEXT NOT NULL,
                year        INTEGER,
                word_count  INTEGER,
                text        TEXT NOT NULL,
                source_url  TEXT,
                source_name TEXT,
                served      INTEGER NOT NULL DEFAULT 0
            )
        """)
        conn.commit()


def insert_work(type, title, author, year, word_count, text, source_url, source_name):
    """Insert one work. Skips duplicates (same title + author + type)."""
    with get_conn() as conn:
        existing = conn.execute(
            "SELECT id FROM works WHERE type=? AND title=? AND author=?",
            (type, title, author)
        ).fetchone()
        if existing:
            return existing["id"]
        cur = conn.execute(
            """INSERT INTO works (type, title, author, year, word_count, text, source_url, source_name)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (type, title, author, year, word_count, text, source_url, source_name)
        )
        conn.commit()
        return cur.lastrowid


def count_by_type():
    """Returns a dict like {'story': 12, 'poem': 45, 'essay': 8}."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT type, COUNT(*) as n FROM works GROUP BY type"
        ).fetchall()
    return {row["type"]: row["n"] for row in rows}


def get_works_by_type(work_type):
    """Return all works of a given type as a list of Row objects."""
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM works WHERE type=?", (work_type,)
        ).fetchall()


def mark_served(work_id):
    with get_conn() as conn:
        conn.execute("UPDATE works SET served=1 WHERE id=?", (work_id,))
        conn.commit()
