"""Unit tests for FreeGamesService."""
# ruff: noqa: PLR2004 — test assertions use literal magic values for clarity

from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import AsyncMock

import pytest

from gaming_hub.data.cache.in_memory import InMemoryCache
from gaming_hub.models.domain.game import Game
from gaming_hub.models.dto.provider import ProviderMetadata, ProviderResult
from gaming_hub.services.free_games_service import FreeGamesService


def _game(  # noqa: PLR0913
    id: str = "1",
    title: str = "Test Game",
    steam_app_id: int | None = None,
    provider_name: str = "test",
    is_free: bool = True,
    free_until: date | None = None,
    coming_soon_date: date | None = None,
    cover_url: str | None = None,
    genres: list[str] | None = None,
    description: str | None = None,
    developers: list[str] | None = None,
) -> Game:
    kwargs = {}
    if cover_url:
        kwargs["cover_url"] = cover_url
    return Game(
        id=id,
        title=title,
        steam_app_id=steam_app_id,
        provider_name=provider_name,
        is_free=is_free,
        free_until=free_until,
        coming_soon_date=coming_soon_date,
        genres=genres or [],
        description=description,
        developers=developers or [],
        **kwargs,
    )


TODAY = date(2026, 7, 17)
TOMORROW = TODAY + timedelta(days=1)
IN_3_DAYS = TODAY + timedelta(days=3)
IN_7_DAYS = TODAY + timedelta(days=7)


@pytest.fixture()
def cache() -> InMemoryCache:
    """Return a fresh in-memory cache."""
    return InMemoryCache(default_ttl=60)


@pytest.fixture()
def mock_providers() -> list[AsyncMock]:
    """Return 3 mocked providers with free game data."""
    p1 = AsyncMock()
    p1.name = "epic"
    p1.get_free_games.return_value = ProviderResult(
        games=[
            _game(
                id="epic-a", title="Free Game A", steam_app_id=100,
                provider_name="epic", free_until=TOMORROW,
                cover_url="http://cover",
            ),
            _game(
                id="epic-b", title="Free Game B", steam_app_id=200,
                provider_name="epic", free_until=IN_3_DAYS,
                cover_url="http://cover",
            ),
        ],
        metadata=ProviderMetadata(provider="epic", returned=2),
    )

    p2 = AsyncMock()
    p2.name = "cheapshark"
    p2.get_free_games.return_value = ProviderResult(
        games=[
            _game(
                id="cs-a", title="Free Game A", steam_app_id=100,
                provider_name="cheapshark", free_until=TOMORROW,
            ),
            _game(
                id="cs-c", title="Free Game C", steam_app_id=300,
                provider_name="cheapshark", free_until=IN_7_DAYS,
                cover_url="http://cover",
            ),
        ],
        metadata=ProviderMetadata(provider="cheapshark", returned=2),
    )

    p3 = AsyncMock()
    p3.name = "steam"
    p3.get_free_games.return_value = ProviderResult(
        games=[], metadata=ProviderMetadata(provider="steam", returned=0),
    )

    return [p1, p2, p3]


@pytest.mark.unit
class TestFreeGamesServiceCurrent:
    """get_current() behavior."""

    @pytest.mark.asyncio
    async def test_get_current_aggregates_all_providers(
        self, cache: InMemoryCache, mock_providers: list[AsyncMock],
    ) -> None:
        """Verify get_current collects games from all non-empty providers."""
        service = FreeGamesService(mock_providers, cache, expiry_hours=48)
        result = await service.get_current()

        assert result.total == 3
        assert len(result.current) == 3
        assert result.fetched_at is not None

    @pytest.mark.asyncio
    async def test_get_current_deduplicates_by_steam_app_id(
        self, cache: InMemoryCache,
    ) -> None:
        """Verify same steam_app_id produces one entry with merged provider_names."""
        p1 = AsyncMock()
        p1.name = "epic"
        p1.get_free_games.return_value = ProviderResult(
            games=[_game(
                id="e1", title="Free Game", steam_app_id=999,
                provider_name="epic", free_until=TOMORROW,
                cover_url="http://cover",
            )],
            metadata=ProviderMetadata(provider="epic", returned=1),
        )
        p2 = AsyncMock()
        p2.name = "cheapshark"
        p2.get_free_games.return_value = ProviderResult(
            games=[_game(
                id="c1", title="Free Game", steam_app_id=999,
                provider_name="cheapshark", free_until=TOMORROW,
            )],
            metadata=ProviderMetadata(provider="cheapshark", returned=1),
        )

        service = FreeGamesService([p1, p2], cache)
        result = await service.get_current()

        assert result.total == 1
        game = result.current[0]
        assert sorted(game.provider_names) == ["cheapshark", "epic"]

    @pytest.mark.asyncio
    async def test_get_current_keeps_earliest_free_until(
        self, cache: InMemoryCache,
    ) -> None:
        """Verify merged game uses the earliest free_until date."""
        p1 = AsyncMock()
        p1.name = "epic"
        p1.get_free_games.return_value = ProviderResult(
            games=[_game(
                id="e1", title="Free Game", steam_app_id=999,
                provider_name="epic", free_until=TOMORROW,
                cover_url="http://cover",
            )],
            metadata=ProviderMetadata(provider="epic", returned=1),
        )
        p2 = AsyncMock()
        p2.name = "cheapshark"
        p2.get_free_games.return_value = ProviderResult(
            games=[_game(
                id="c1", title="Free Game", steam_app_id=999,
                provider_name="cheapshark", free_until=IN_7_DAYS,
            )],
            metadata=ProviderMetadata(provider="cheapshark", returned=1),
        )

        service = FreeGamesService([p1, p2], cache)
        result = await service.get_current()

        assert result.total == 1
        assert result.current[0].free_until == TOMORROW

    @pytest.mark.asyncio
    async def test_get_current_expiry_sorting(
        self, cache: InMemoryCache,
    ) -> None:
        """Verify games are sorted by free_until ascending."""
        p = AsyncMock()
        p.name = "epic"
        p.get_free_games.return_value = ProviderResult(
            games=[
                _game(
                    id="a", title="Later Game", steam_app_id=100,
                    provider_name="epic", free_until=IN_7_DAYS,
                ),
                _game(
                    id="b", title="Sooner Game", steam_app_id=200,
                    provider_name="epic", free_until=TOMORROW,
                ),
                _game(id="c", title="No Expiry", steam_app_id=300, provider_name="epic"),
            ],
            metadata=ProviderMetadata(provider="epic", returned=3),
        )

        service = FreeGamesService([p], cache)
        result = await service.get_current()

        titles = [g.title for g in result.current]
        assert titles == ["Sooner Game", "Later Game", "No Expiry"]

    @pytest.mark.asyncio
    async def test_get_current_expiring_soon_filter(
        self, cache: InMemoryCache,
    ) -> None:
        """Verify expiring_soon only includes games within expiry_hours."""
        p = AsyncMock()
        p.name = "epic"
        p.get_free_games.return_value = ProviderResult(
            games=[
                _game(
                    id="a", title="Expiring Soon", steam_app_id=100,
                    provider_name="epic", free_until=TOMORROW,
                ),
                _game(
                    id="b", title="Not Expiring", steam_app_id=200,
                    provider_name="epic", free_until=IN_7_DAYS,
                ),
            ],
            metadata=ProviderMetadata(provider="epic", returned=2),
        )

        service = FreeGamesService([p], cache, expiry_hours=48)
        result = await service.get_current()

        assert len(result.expiring_soon) == 1
        assert result.expiring_soon[0].title == "Expiring Soon"

    @pytest.mark.asyncio
    async def test_get_current_empty_week(
        self, cache: InMemoryCache,
    ) -> None:
        """Verify empty result when no providers have free games."""
        p = AsyncMock()
        p.name = "epic"
        p.get_free_games.return_value = ProviderResult(
            games=[], metadata=ProviderMetadata(provider="epic", returned=0),
        )

        service = FreeGamesService([p], cache)
        result = await service.get_current()

        assert result.total == 0
        assert len(result.current) == 0
        assert len(result.expiring_soon) == 0

    @pytest.mark.asyncio
    async def test_get_current_provider_error_isolation(
        self, cache: InMemoryCache,
    ) -> None:
        """Verify one failing provider doesn't block results."""
        p1 = AsyncMock()
        p1.name = "good"
        p1.get_free_games.return_value = ProviderResult(
            games=[_game(
                id="g1", title="Good Game", steam_app_id=100,
                provider_name="good", free_until=TOMORROW,
            )],
            metadata=ProviderMetadata(provider="good", returned=1),
        )
        p2 = AsyncMock()
        p2.name = "broken"
        p2.get_free_games.side_effect = ValueError("Boom")

        service = FreeGamesService([p1, p2], cache)
        result = await service.get_current()

        assert result.total == 1
        assert len(result.errors) >= 1

    @pytest.mark.asyncio
    async def test_get_current_empty_provider(
        self, cache: InMemoryCache,
    ) -> None:
        """Verify a provider returning no games doesn't cause errors."""
        p = AsyncMock()
        p.name = "empty"
        p.get_free_games.return_value = ProviderResult(
            games=[], metadata=ProviderMetadata(provider="empty", returned=0),
        )

        service = FreeGamesService([p], cache)
        result = await service.get_current()

        assert result.total == 0
        assert len(result.errors) == 0


@pytest.mark.unit
class TestFreeGamesServiceUpcoming:
    """get_upcoming() behavior."""

    @pytest.mark.asyncio
    async def test_get_upcoming_only_epic(
        self, cache: InMemoryCache,
    ) -> None:
        """Verify get_upcoming only queries the Epic provider."""
        p_epic = AsyncMock()
        p_epic.name = "epic"
        p_epic.get_free_games.return_value = ProviderResult(
            games=[_game(
                id="up1", title="Upcoming Game", steam_app_id=500,
                provider_name="epic", coming_soon_date=IN_3_DAYS,
            )],
            metadata=ProviderMetadata(provider="epic", returned=1),
        )
        p_other = AsyncMock()
        p_other.name = "cheapshark"
        p_other.get_free_games = AsyncMock()

        service = FreeGamesService([p_epic, p_other], cache)
        result = await service.get_upcoming()

        assert result.total == 1
        assert result.current[0].title == "Upcoming Game"
        p_other.get_free_games.assert_not_called()


@pytest.mark.unit
class TestFreeGamesServiceHelpers:
    """Merge and scoring helpers."""

    def test_merge_free_games_combines_provider_names(self) -> None:
        """Verify merged game has combined provider_names."""
        games = [
            _game(
                id="a", title="Same Game", steam_app_id=999,
                provider_name="epic", free_until=TOMORROW,
                cover_url="http://cover",
            ),
            _game(
                id="b", title="Same Game", steam_app_id=999,
                provider_name="cheapshark", free_until=IN_3_DAYS,
            ),
        ]
        merged = FreeGamesService._merge_free_games(games)
        assert len(merged) == 1
        assert sorted(merged[0].provider_names) == ["cheapshark", "epic"]

    def test_completeness_score_richer_data_wins(self) -> None:
        """Verify richer data replaces poorer during merge."""
        poor = _game(
            id="a", title="Same Game", steam_app_id=999, provider_name="epic",
        )
        rich = _game(
            id="b", title="Same Game", steam_app_id=999,
            provider_name="cheapshark", cover_url="http://cover",
            genres=["Action"], description="A" * 60, developers=["DevCo"],
        )
        merged = FreeGamesService._merge_free_games([poor, rich])
        assert len(merged) == 1
        assert merged[0].provider_name == "cheapshark"

    def test_merge_free_games_preserves_distinct_games(self) -> None:
        """Verify different games are not merged."""
        games = [
            _game(id="a", title="Game A", steam_app_id=100, provider_name="epic"),
            _game(id="b", title="Game B", steam_app_id=200, provider_name="cheapshark"),
        ]
        merged = FreeGamesService._merge_free_games(games)
        assert len(merged) == 2

    def test_completeness_score_empty(self) -> None:
        """Verify minimum completeness score."""
        game = _game()
        score = FreeGamesService._completeness_score(game)
        assert score == 0

    def test_completeness_score_full(self) -> None:
        """Verify maximum completeness score (all fields populated)."""
        game = _game(
            cover_url="http://cover", genres=["Action"],
            description="A" * 60, developers=["DevCo"],
        )
        score = FreeGamesService._completeness_score(game)
        assert score == 4

    def test_filter_expiring_soon(self) -> None:
        """Verify _filter_expiring_soon returns games within expiry window."""
        games = [
            _game(id="a", title="Soon", free_until=TOMORROW),
            _game(id="b", title="Far", free_until=IN_7_DAYS),
            _game(id="c", title="No Date"),
        ]
        service = FreeGamesService([], cache=InMemoryCache(), expiry_hours=48)
        result = service._filter_expiring_soon(games)
        assert len(result) == 1
        assert result[0].title == "Soon"
