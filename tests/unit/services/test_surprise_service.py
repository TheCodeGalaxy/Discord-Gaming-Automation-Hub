"""Unit tests for SurpriseService."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from gaming_hub.data.cache.in_memory import InMemoryCache
from gaming_hub.models.domain.game import Game
from gaming_hub.services.surprise_service import SurpriseService


def _game(
    id: str = "1",
    title: str = "Test Game",
    genres: list[str] | None = None,
    tags: list[str] | None = None,
    provider_name: str = "test",
) -> Game:
    return Game(
        id=id,
        title=title,
        genres=genres or [],
        tags=tags or [],
        provider_name=provider_name,
    )


@pytest.fixture()
def cache() -> InMemoryCache:
    """Return a fresh in-memory cache."""
    return InMemoryCache(default_ttl=60)


@pytest.mark.unit
class TestSurpriseServiceGetRandom:
    """get_random() behavior."""

    @pytest.mark.asyncio
    async def test_get_random_returns_game(self, cache: InMemoryCache) -> None:
        """Verify get_random returns a valid Game when pool is non-empty."""
        service = SurpriseService([], cache)

        pool = [
            _game(id="g1", title="Game One"),
            _game(id="g2", title="Game Two"),
        ]

        with patch.object(service, "_build_pool", return_value=pool):
            result = await service.get_random(session_id="test-session")

        assert result is not None
        assert result.title in ("Game One", "Game Two")

    @pytest.mark.asyncio
    async def test_get_random_returns_none_on_empty_pool(
        self,
        cache: InMemoryCache,
    ) -> None:
        """Verify get_random returns None when pool is empty."""
        service = SurpriseService([], cache)

        with patch.object(service, "_build_pool", return_value=[]):
            result = await service.get_random(session_id="test-session")

        assert result is None

    @pytest.mark.asyncio
    async def test_history_prevents_repeats_in_same_session(
        self,
        cache: InMemoryCache,
    ) -> None:
        """Verify same session gets different games on sequential calls."""
        service = SurpriseService([], cache)

        pool = [
            _game(id="g1", title="Game One"),
            _game(id="g2", title="Game Two"),
        ]

        with patch.object(service, "_build_pool", return_value=pool):
            first = await service.get_random(session_id="same")
            second = await service.get_random(session_id="same")

        assert first is not None
        assert second is not None
        assert first.id != second.id

    @pytest.mark.asyncio
    async def test_different_sessions_can_get_same_game(
        self,
        cache: InMemoryCache,
    ) -> None:
        """Verify different sessions can independently get the same game."""
        service = SurpriseService([], cache)

        pool = [_game(id="g1", title="Game One")]

        with patch.object(service, "_build_pool", return_value=pool):
            first = await service.get_random(session_id="session-a")
            second = await service.get_random(session_id="session-b")

        assert first is not None
        assert second is not None
        assert first.id == second.id

    @pytest.mark.asyncio
    async def test_pool_exhaustion_resets_history(
        self,
        cache: InMemoryCache,
    ) -> None:
        """Verify exhausted pool resets and returns a game."""
        service = SurpriseService([], cache)

        pool = [_game(id="g1", title="Only Game")]

        with patch.object(service, "_build_pool", return_value=pool):
            first = await service.get_random(session_id="test")
            second = await service.get_random(session_id="test")

        assert first is not None
        assert second is not None
        assert first.id == second.id

    @pytest.mark.asyncio
    async def test_genre_filter_returns_only_matching(
        self,
        cache: InMemoryCache,
    ) -> None:
        """Verify genre parameter filters pool to matching games."""
        service = SurpriseService([], cache)

        pool = [
            _game(id="g1", title="RPG Game", genres=["RPG"]),
            _game(id="g2", title="Action Game", genres=["Action"]),
        ]

        with patch.object(service, "_build_pool", return_value=pool):
            result = await service.get_random(session_id="test", genre="RPG")

        assert result is not None
        assert result.title == "RPG Game"

    @pytest.mark.asyncio
    async def test_genre_filter_matches_tags_fallback(
        self,
        cache: InMemoryCache,
    ) -> None:
        """Verify genre parameter also matches against tags."""
        service = SurpriseService([], cache)

        pool = [
            _game(id="g1", title="Surprise Game", tags=["roguelike"]),
        ]

        with patch.object(service, "_build_pool", return_value=pool):
            result = await service.get_random(session_id="test", genre="roguelike")

        assert result is not None
        assert result.title == "Surprise Game"

    @pytest.mark.asyncio
    async def test_genre_param_filters_correctly(
        self,
        cache: InMemoryCache,
    ) -> None:
        """Verify explicit genre parameter filters the pool."""
        service = SurpriseService([], cache)

        pool = [
            _game(id="g1", title="RPG Game", genres=["RPG"]),
            _game(id="g2", title="Action Game", genres=["Action"]),
        ]

        with patch.object(service, "_build_pool", return_value=pool):
            result = await service.get_random(session_id="test", genre="RPG")

        assert result is not None
        assert result.title == "RPG Game"


@pytest.mark.unit
class TestSurpriseServiceMatchesGenre:
    """_matches_genre() behavior."""

    def test_matches_genre_by_name(self) -> None:
        """Verify _matches_genre returns True when genre matches."""
        service = SurpriseService([], InMemoryCache(), favorite_genres=["RPG"])
        game = _game(genres=["RPG", "Action"])
        assert service._matches_genre(game) is True

    def test_no_match(self) -> None:
        """Verify _matches_genre returns False for non-matching game."""
        service = SurpriseService([], InMemoryCache(), favorite_genres=["RPG"])
        game = _game(genres=["Strategy"])
        assert service._matches_genre(game) is False

    def test_empty_favorites(self) -> None:
        """Verify _matches_genre returns True when no favorites set."""
        service = SurpriseService([], InMemoryCache(), favorite_genres=[])
        game = _game(genres=["Anything"])
        assert service._matches_genre(game) is True
