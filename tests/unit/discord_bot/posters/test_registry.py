"""Tests for PosterRegistry."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from gaming_hub.discord_bot.posters import PosterRegistry


@pytest.mark.unit
class TestPosterRegistry:
    """PosterRegistry behavior."""

    def test_register_and_get(self) -> None:
        """Verify register/get round-trip."""
        registry = PosterRegistry()
        poster = MagicMock()
        registry.register("post_test", poster)
        assert registry.get("post_test") is poster

    def test_get_unknown_returns_none(self) -> None:
        """Verify unknown action returns None."""
        registry = PosterRegistry()
        assert registry.get("post_nonexistent") is None

    def test_all_returns_copy(self) -> None:
        """Verify all() returns a dict copy."""
        registry = PosterRegistry()
        poster = MagicMock()
        registry.register("post_test", poster)
        all_posters = registry.all()
        assert all_posters == {"post_test": poster}
