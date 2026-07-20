"""Calendar repository — SQLite-backed reminder deduplication.

Tracks which calendar events have already triggered reminders so the same
event does not produce duplicate notifications on consecutive checks.
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class CalendarRepository:
    """Persist and query reminder-sent state for calendar events.

    Uses a single SQLite table (``reminder_sent``) with columns
    ``event_id`` (TEXT PRIMARY KEY) and ``sent_at`` (TEXT ISO timestamp).
    The database file lives alongside the application data.
    """

    def __init__(self, db_path: str | Path | None = None) -> None:
        """Open or create the SQLite database.

        Args:
            db_path: Path to the SQLite file. Defaults to
                     ``data/calendar_reminders.db`` in the project root.
        """
        if db_path is None:
            db_path = Path(__file__).parents[3] / "data" / "calendar_reminders.db"
        self._db_path = str(db_path)
        self._init_db()

    def _init_db(self) -> None:
        """Create the ``reminder_sent`` table if it does not exist."""
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS reminder_sent ("
                "  event_id TEXT PRIMARY KEY,"
                "  sent_at TEXT NOT NULL"
                ")"
            )

    def mark_sent(self, event_id: str) -> None:
        """Record that a reminder has been sent for an event.

        Args:
            event_id: The Google Calendar event ID.
        """
        now = datetime.now(UTC).isoformat()
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO reminder_sent (event_id, sent_at) VALUES (?, ?)",
                (event_id, now),
            )

    def is_sent(self, event_id: str) -> bool:
        """Return True if a reminder has already been sent for ``event_id``.

        Args:
            event_id: The Google Calendar event ID.

        Returns:
            True if the event ID exists in the table.
        """
        with sqlite3.connect(self._db_path) as conn:
            row = conn.execute(
                "SELECT 1 FROM reminder_sent WHERE event_id = ?",
                (event_id,),
            ).fetchone()
            return row is not None

    def stats(self) -> dict[str, Any]:
        """Return simple statistics about the tracking table.

        Returns:
            A dict with ``total_tracked`` count.
        """
        with sqlite3.connect(self._db_path) as conn:
            row = conn.execute("SELECT COUNT(*) FROM reminder_sent").fetchone()
            return {"total_tracked": row[0] if row else 0}

    def clear(self) -> None:
        """Delete all reminder records (for testing)."""
        with sqlite3.connect(self._db_path) as conn:
            conn.execute("DELETE FROM reminder_sent")
