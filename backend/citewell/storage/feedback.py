"""
Feedback storage for Citewell, backed by SQLite.

SQLite is safe for the concurrent writes that happen once the app is deployed
(several users, or several tabs), stays a single portable file, and needs no
database server, which suits a free-tier deployment. Compared with a CSV file
it cannot interleave or corrupt rows.

Each row stores the question, answer, sources, mode and retrieval settings, not
just a thumbs up/down, so feedback can actually be analysed later (which
questions are rated down, whether a higher top_k correlates with better
ratings) or promoted into the evaluation set.

This module is plain Python with no Streamlit dependency, so it is directly
unit-testable.
"""

import logging
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from citewell import config

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 1
VALID_RATINGS = ("up", "down")
MAX_FIELD_CHARS = 20_000  # cap stored text so one request cannot bloat the database


@dataclass
class FeedbackEntry:
    question: str
    answer: str
    sources: List[str]
    rating: str  # "up" or "down"
    mode: str  # which document set was queried
    top_k: int
    timestamp: str = ""


def _connect(db_path: Optional[Path] = None) -> sqlite3.Connection:
    db_path = Path(db_path or config.DATABASE_PATH)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(db_path), timeout=10)
    try:
        conn.execute("PRAGMA journal_mode=WAL")  # readers do not block the writer
    except sqlite3.DatabaseError:
        logger.debug("WAL mode unavailable for %s", db_path)  # e.g. some network file systems

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            question TEXT NOT NULL,
            answer TEXT NOT NULL,
            sources TEXT,
            rating TEXT NOT NULL CHECK (rating IN ('up', 'down')),
            mode TEXT NOT NULL,
            top_k INTEGER NOT NULL
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_feedback_rating ON feedback (rating)")
    conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
    return conn


def log_feedback(entry: FeedbackEntry, db_path: Optional[Path] = None) -> None:
    """Persist one feedback entry. Raises ValueError for an invalid rating."""
    if entry.rating not in VALID_RATINGS:
        raise ValueError(f"rating must be one of {VALID_RATINGS}, got {entry.rating!r}")

    timestamp = entry.timestamp or datetime.now(timezone.utc).isoformat()
    sources_joined = " | ".join(entry.sources)[:MAX_FIELD_CHARS]

    with closing(_connect(db_path)) as conn, conn:  # `with conn` commits or rolls back
        conn.execute(
            "INSERT INTO feedback (timestamp, question, answer, sources, rating, mode, top_k) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                timestamp,
                entry.question[:MAX_FIELD_CHARS],
                entry.answer[:MAX_FIELD_CHARS],
                sources_joined,
                entry.rating,
                entry.mode,
                int(entry.top_k),
            ),
        )


def get_feedback_summary(db_path: Optional[Path] = None) -> dict:
    """Aggregate counts, e.g. {"up": 12, "down": 2}."""
    counts = {"up": 0, "down": 0}
    with closing(_connect(db_path)) as conn:
        for rating, count in conn.execute("SELECT rating, COUNT(*) FROM feedback GROUP BY rating"):
            if rating in counts:
                counts[rating] = count
    return counts


def get_all_feedback(db_path: Optional[Path] = None) -> List[dict]:
    """Every feedback row as a dict, most recent first."""
    with closing(_connect(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        return [dict(row) for row in conn.execute("SELECT * FROM feedback ORDER BY id DESC")]
