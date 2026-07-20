"""In-memory session-based history tracker.

Used by ``SurpriseService`` to avoid replaying the same game to the same
session. Designed to be swappable for a database-backed implementation.
"""

from __future__ import annotations


class InMemoryHistoryTracker:
    """Track seen game IDs per session ID.

    Stores history in a dict keyed by ``session_id``. State is lost on
    process restart.
    """

    def __init__(self) -> None:
        """Initialize an empty history store."""
        self._store: dict[str, list[str]] = {}

    def mark_seen(self, session_id: str, game_id: str) -> None:
        """Record that ``game_id`` has been seen in ``session_id``."""
        self._store.setdefault(session_id, []).append(game_id)

    def get_seen(self, session_id: str) -> list[str]:
        """Return all game IDs seen in ``session_id``."""
        return self._store.get(session_id, [])

    def reset(self, session_id: str) -> None:
        """Clear history for a single session."""
        self._store[session_id] = []

    def is_seen(self, session_id: str, game_id: str) -> bool:
        """Return True if ``game_id`` has been seen in ``session_id``."""
        return game_id in self._store.get(session_id, [])

    def reset_all(self) -> None:
        """Clear history for all sessions."""
        self._store.clear()
