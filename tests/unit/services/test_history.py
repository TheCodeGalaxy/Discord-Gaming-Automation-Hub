"""Unit tests for InMemoryHistoryTracker."""

from __future__ import annotations

import pytest

from gaming_hub.services.history import InMemoryHistoryTracker


@pytest.mark.unit
class TestInMemoryHistoryTracker:
    """InMemoryHistoryTracker behavior."""

    def test_mark_seen_and_get_seen_round_trip(self) -> None:
        """Verify marked game IDs are returned by get_seen."""
        tracker = InMemoryHistoryTracker()
        tracker.mark_seen("session-a", "game-1")
        tracker.mark_seen("session-a", "game-2")
        assert tracker.get_seen("session-a") == ["game-1", "game-2"]

    def test_get_seen_unknown_session_returns_empty(self) -> None:
        """Verify get_seen returns empty list for unknown session."""
        tracker = InMemoryHistoryTracker()
        assert tracker.get_seen("unknown") == []

    def test_reset_clears_session_only(self) -> None:
        """Verify reset clears only the targeted session."""
        tracker = InMemoryHistoryTracker()
        tracker.mark_seen("session-a", "game-1")
        tracker.mark_seen("session-b", "game-2")
        tracker.reset("session-a")
        assert tracker.get_seen("session-a") == []
        assert tracker.get_seen("session-b") == ["game-2"]

    def test_reset_all_clears_everything(self) -> None:
        """Verify reset_all clears all sessions."""
        tracker = InMemoryHistoryTracker()
        tracker.mark_seen("session-a", "game-1")
        tracker.mark_seen("session-b", "game-2")
        tracker.reset_all()
        assert tracker.get_seen("session-a") == []
        assert tracker.get_seen("session-b") == []

    def test_is_seen_returns_true_for_marked_game(self) -> None:
        """Verify is_seen returns True for a seen game."""
        tracker = InMemoryHistoryTracker()
        tracker.mark_seen("session-a", "game-1")
        assert tracker.is_seen("session-a", "game-1") is True

    def test_is_seen_returns_false_for_unseen_game(self) -> None:
        """Verify is_seen returns False for an unseen game."""
        tracker = InMemoryHistoryTracker()
        tracker.mark_seen("session-a", "game-1")
        assert tracker.is_seen("session-a", "game-2") is False

    def test_is_seen_unknown_session(self) -> None:
        """Verify is_seen returns False for unknown session."""
        tracker = InMemoryHistoryTracker()
        assert tracker.is_seen("unknown", "game-1") is False
