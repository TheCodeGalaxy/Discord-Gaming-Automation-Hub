"""Unit tests for NewReleasesService."""
# ruff: noqa: PLR2004 — test assertions use literal magic values for clarity

from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import AsyncMock

import pytest

from gaming_hub.data.cache.in_memory import InMemoryCache
from gaming_hub.models.domain.game import Game
from gaming_hub.models.dto.provider import ProviderMetadata, ProviderResult
from gaming_hub.services.new_releases_service import NewReleasesService

TODAY = date.today()
TOMORROW = TODAY + timedelta(days=1)
IN_10_DAYS = TODAY + timedelta(days=10)
IN_20_DAYS = TODAY + timedelta(days=20)
IN_40_DAYS = TODAY + timedelta(days=40)
YESTERDAY = TODAY - timedelta(days=1)


def _game(  # noqa: PLR0913
    id: str = "1",
    title: str = "Test Game",
    steam_app_id: int | None = None,
    release_date: date | None = None,
    cover_url: str | None = None,
    description: str | None = None,
    genres: list[str] | None = None,
    developers: list[str] | None = None,
    provider_name: str = "test",
) -> Game:
    kwargs: dict = {}
    if cover_url:
        kwargs["cover_url"] = cover_url
    return Game(
        id=id,
        title=title,
        steam_app_id=steam_app_id,
        release_date=release_date,
        genres=genres or [],
        description=description,
        developers=developers or [],
        provider_name=provider_name,
        **kwargs,
    )


@pytest.fixture()
def cache() -> InMemoryCache:
    """Return a fresh in-memory cache."""
    return InMemoryCache(default_ttl=60)


@pytest.fixture()
def mock_providers() -> list[AsyncMock]:
    """Return 2 mocked providers with upcoming games."""
    p1 = AsyncMock()
    p1.name = "provider-a"
    p1.get_deals.return_value = ProviderResult(
        metadata=ProviderMetadata(provider="provider-a", returned=0),
    )
    # no get_new_releases — falls back to empty

    p2 = AsyncMock()
    p2.name = "provider-b"
    p2.get_deals.return_value = ProviderResult(
        metadata=ProviderMetadata(provider="provider-b", returned=0),
    )

    return [p1, p2]


@pytest.mark.unit
class TestNewReleasesServiceGetUpcoming:
    """get_upcoming() behavior."""

    @pytest.mark.asyncio
    async def test_date_filtering(
        self,
        cache: InMemoryCache,
    ) -> None:
        """Verify games outside date range are excluded."""
        games = [
            _game(id="past", title="Past Game", release_date=YESTERDAY, steam_app_id=1),
            _game(id="soon", title="Soon Game", release_date=IN_10_DAYS, steam_app_id=2),
            _game(id="cutoff", title="Cutoff Game", release_date=IN_40_DAYS, steam_app_id=3),
        ]

        merged = NewReleasesService._merge_upcoming(games)
        today = date.today()
        cutoff = today + timedelta(days=30)
        filtered = [g for g in merged if g.release_date and today <= g.release_date <= cutoff]
        assert len(filtered) == 1
        assert filtered[0].title == "Soon Game"

    @pytest.mark.asyncio
    async def test_deduplication_by_steam_app_id(
        self,
        cache: InMemoryCache,
    ) -> None:
        """Verify same steam_app_id from two providers yields one entry."""
        service = NewReleasesService([], cache)

        games = [
            _game(
                id="a",
                title="Same Game",
                steam_app_id=999,
                release_date=IN_10_DAYS,
                provider_name="provider-a",
            ),
            _game(
                id="b",
                title="Same Game",
                steam_app_id=999,
                release_date=IN_10_DAYS,
                provider_name="provider-b",
            ),
        ]
        merged = service._merge_upcoming(games)
        assert len(merged) == 1
        assert sorted(merged[0].provider_names) == ["provider-a", "provider-b"]

    @pytest.mark.asyncio
    async def test_sorting_by_release_date(
        self,
        cache: InMemoryCache,
    ) -> None:
        """Verify games are sorted by release_date ascending."""
        service = NewReleasesService([], cache)

        games = [
            _game(
                id="c",
                title="Later Game",
                steam_app_id=3,
                release_date=IN_20_DAYS,
                provider_name="test",
            ),
            _game(
                id="a",
                title="Sooner Game",
                steam_app_id=1,
                release_date=TOMORROW,
                provider_name="test",
            ),
            _game(
                id="b",
                title="Middle Game",
                steam_app_id=2,
                release_date=IN_10_DAYS,
                provider_name="test",
            ),
        ]
        merged = service._merge_upcoming(games)
        merged.sort(key=lambda g: g.release_date or date.max)
        titles = [g.title for g in merged]
        assert titles == ["Sooner Game", "Middle Game", "Later Game"]

    @pytest.mark.asyncio
    async def test_empty_result_when_no_games(
        self,
        cache: InMemoryCache,
    ) -> None:
        """Verify empty result when no providers return games."""
        p = AsyncMock()
        p.name = "empty"
        p.get_deals.return_value = ProviderResult(
            metadata=ProviderMetadata(provider="empty", returned=0),
        )

        service = NewReleasesService([p], cache)
        result = await service.get_upcoming(days_ahead=30, limit=20)

        assert result.total == 0
        assert len(result.games) == 0

    @pytest.mark.asyncio
    async def test_limit_applied(
        self,
        cache: InMemoryCache,
    ) -> None:
        """Verify limit restricts the number of returned games."""
        service = NewReleasesService([], cache)

        games = [
            _game(
                id=str(i),
                title=f"Game {i}",
                steam_app_id=i,
                release_date=IN_10_DAYS,
                provider_name="test",
            )
            for i in range(10)
        ]
        merged = service._merge_upcoming(games)
        limited = merged[:3]
        assert len(limited) <= 3


@pytest.mark.unit
class TestNewReleasesServiceMerge:
    """_merge_upcoming() behavior."""

    def test_merge_keeps_richer_data(self) -> None:
        """Verify richer data replaces poorer during merge."""
        service = NewReleasesService([], InMemoryCache())

        poor = _game(
            id="a",
            title="Same Game",
            steam_app_id=999,
            release_date=IN_10_DAYS,
            provider_name="provider-a",
        )
        rich = _game(
            id="b",
            title="Same Game",
            steam_app_id=999,
            release_date=IN_10_DAYS,
            provider_name="provider-b",
            cover_url="http://cover",
            description="Rich description",
            genres=["Action"],
            developers=["DevCo"],
        )
        merged = service._merge_upcoming([poor, rich])
        assert len(merged) == 1
        assert merged[0].provider_name == "provider-b"

    def test_merge_preserves_distinct_games(self) -> None:
        """Verify different games are not merged."""
        service = NewReleasesService([], InMemoryCache())

        games = [
            _game(
                id="a",
                title="Game A",
                steam_app_id=100,
                release_date=IN_10_DAYS,
                provider_name="p1",
            ),
            _game(
                id="b",
                title="Game B",
                steam_app_id=200,
                release_date=IN_20_DAYS,
                provider_name="p2",
            ),
        ]
        merged = service._merge_upcoming(games)
        assert len(merged) == 2


@pytest.mark.unit
class TestNewReleasesServiceRichness:
    """_richness() behavior."""

    def test_richness_empty(self) -> None:
        """Verify minimum richness score."""
        game = _game(steam_app_id=1, release_date=IN_10_DAYS)
        score = NewReleasesService._richness(game)
        assert score == 0

    def test_richness_full(self) -> None:
        """Verify maximum richness score (all fields populated)."""
        game = _game(
            steam_app_id=1,
            release_date=IN_10_DAYS,
            cover_url="http://cover",
            description="Full",
            genres=["Action"],
            developers=["DevCo"],
        )
        score = NewReleasesService._richness(game)
        assert score == 4
