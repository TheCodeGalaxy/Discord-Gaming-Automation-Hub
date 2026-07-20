"""Tests for UserPreferences domain entity."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from gaming_hub.models.domain.user import UserPreferences


class TestUserPreferences:
    """UserPreferences entity construction and defaults."""

    @pytest.mark.unit
    def test_default_construction(self) -> None:
        """UserPreferences should provide sensible defaults."""
        prefs = UserPreferences()
        assert prefs.discord_user_id is None
        assert prefs.favorite_genres == []
        assert prefs.ignored_stores == []
        assert prefs.ignored_tags == []
        assert prefs.surprise_history == []
        threshold = 50
        assert prefs.discount_threshold == threshold
        assert prefs.created_at is not None
        assert prefs.updated_at is not None

    @pytest.mark.unit
    def test_partial_construction(self) -> None:
        """UserPreferences should accept partial field overrides."""
        user_id = 12345
        threshold = 50
        prefs = UserPreferences(
            discord_user_id=user_id,
            favorite_genres=["RPG", "Strategy"],
        )
        assert prefs.discord_user_id == user_id
        assert prefs.favorite_genres == ["RPG", "Strategy"]
        assert prefs.discount_threshold == threshold

    @pytest.mark.unit
    def test_full_construction(self) -> None:
        """UserPreferences should construct with all fields."""
        threshold = 75
        history_count = 3
        prefs = UserPreferences(
            discord_user_id=67890,
            favorite_genres=["Action"],
            ignored_stores=["epic"],
            ignored_tags=["early-access"],
            surprise_history=["g1", "g2", "g3"],
            discount_threshold=threshold,
        )
        assert prefs.discount_threshold == threshold
        assert prefs.ignored_stores == ["epic"]
        assert len(prefs.surprise_history) == history_count

    @pytest.mark.unit
    def test_discount_threshold_bounds(self) -> None:
        """UserPreferences should reject out-of-range discount_threshold."""
        with pytest.raises(ValidationError):
            UserPreferences(discount_threshold=-1)
        with pytest.raises(ValidationError):
            UserPreferences(discount_threshold=101)

    @pytest.mark.unit
    def test_json_roundtrip(self) -> None:
        """UserPreferences should survive JSON serialization roundtrip."""
        user_id = 12345
        threshold = 60
        prefs = UserPreferences(
            discord_user_id=user_id,
            favorite_genres=["RPG"],
            discount_threshold=threshold,
        )
        data = prefs.model_dump_json()
        restored = UserPreferences.model_validate_json(data)
        assert restored == prefs
        assert restored.favorite_genres == ["RPG"]
        assert restored.discount_threshold == threshold
