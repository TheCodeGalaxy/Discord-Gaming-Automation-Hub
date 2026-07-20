"""Unit tests for DiscountService."""
# ruff: noqa: PLR2004 — test assertions use literal magic values for clarity

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from gaming_hub.core.enums import StoreName
from gaming_hub.data.cache.in_memory import InMemoryCache
from gaming_hub.models.domain.deal import Deal
from gaming_hub.models.dto.provider import ProviderMetadata, ProviderResult
from gaming_hub.services.discount_service import DiscountService

STEAM_APP_1 = "https://store.steampowered.com/app/1"
STEAM_APP_2 = "https://store.steampowered.com/app/2"
STEAM_APP_3 = "https://store.steampowered.com/app/3"
STEAM_APP_4 = "https://store.steampowered.com/app/4"
STEAM_APP_10 = "https://store.steampowered.com/app/10"
STEAM_APP_11 = "https://store.steampowered.com/app/11"
STEAM_APP_12 = "https://store.steampowered.com/app/12"
STEAM_APP_20 = "https://store.steampowered.com/app/20"
STEAM_APP_99 = "https://store.steampowered.com/app/99"
STEAM_APP_100 = "https://store.steampowered.com/app/100"
STEAM_APP_200 = "https://store.steampowered.com/app/200"
STEAM_APP_301 = "https://store.steampowered.com/app/301"
STEAM_APP_500 = "https://store.steampowered.com/app/500"
EPIC_GAME_URL = "https://store.epicgames.com/p/epic1"
EPIC_GAMEB_URL = "https://store.epicgames.com/p/gameb"


def _deal(  # noqa: PLR0913
    id: str = "1",
    title: str = "Test Deal",
    store: StoreName = StoreName.Steam,
    store_url: str | None = None,
    current_price: float = 5.0,
    original_price: float | None = 50.0,
    discount_percent: float = 80.0,
    provider_name: str = "test",
    raw_metadata: dict | None = None,
) -> Deal:
    kwargs: dict = {}
    if store_url:
        kwargs["store_url"] = store_url
    return Deal(
        id=id,
        title=title,
        store=store,
        current_price=current_price,
        original_price=original_price,
        discount_percent=discount_percent,
        provider_names=[provider_name],
        raw_metadata=raw_metadata or {},
        **kwargs,
    )


@pytest.fixture()
def cache() -> InMemoryCache:
    """Return a fresh in-memory cache."""
    return InMemoryCache(default_ttl=60)


@pytest.fixture()
def mock_providers() -> list[AsyncMock]:
    """Return 3 mocked providers with known deal lists."""
    p1 = AsyncMock()
    p1.name = "cheapshark"
    p1.get_deals.return_value = ProviderResult(
        deals=[
            _deal(
                id="cs-1",
                title="Deep Discount",
                discount_percent=90.0,
                current_price=5.0,
                original_price=50.0,
                store_url=STEAM_APP_1,
                provider_name="cheapshark",
            ),
            _deal(
                id="cs-2",
                title="Moderate Deal",
                discount_percent=50.0,
                current_price=10.0,
                original_price=20.0,
                store_url=STEAM_APP_2,
                provider_name="cheapshark",
            ),
            _deal(
                id="cs-3",
                title="Threshold Deal",
                discount_percent=80.0,
                current_price=15.0,
                original_price=75.0,
                store_url=STEAM_APP_3,
                provider_name="cheapshark",
            ),
        ],
        metadata=ProviderMetadata(provider="cheapshark", returned=3),
    )

    p2 = AsyncMock()
    p2.name = "epic"
    p2.get_deals.return_value = ProviderResult(
        deals=[
            _deal(
                id="epic-1",
                title="Epic Deal",
                discount_percent=85.0,
                current_price=7.5,
                original_price=50.0,
                store_url=EPIC_GAME_URL,
                provider_name="epic",
            ),
        ],
        metadata=ProviderMetadata(provider="epic", returned=1),
    )

    p3 = AsyncMock()
    p3.name = "isthereanydeal"
    p3.get_deals.return_value = ProviderResult(
        deals=[
            _deal(
                id="itad-1",
                title="ITAD Deal",
                discount_percent=82.0,
                current_price=9.0,
                original_price=50.0,
                store_url=STEAM_APP_4,
                provider_name="isthereanydeal",
                raw_metadata={"itad_plain_id": "itad_deal_1"},
            ),
        ],
        metadata=ProviderMetadata(provider="isthereanydeal", returned=1),
    )
    p3.get_lowest_price = AsyncMock(
        return_value={
            "plain_id": "itad_deal_1",
            "lowest_price": 5.0,
            "lowest_recorded_date": "2025-01-01",
        }
    )

    return [p1, p2, p3]


@pytest.mark.unit
class TestDiscountServiceCrazyDiscounts:
    """get_crazy_discounts() behavior."""

    @pytest.mark.asyncio
    async def test_threshold_filter(
        self,
        cache: InMemoryCache,
        mock_providers: list[AsyncMock],
    ) -> None:
        """Verify only deals with discount_percent >= threshold are returned."""
        service = DiscountService(mock_providers, cache, discount_threshold=80.0)
        result = await service.get_crazy_discounts(limit=10)

        assert result.total >= 3  # 90%, 80%, 85%, 82% all pass
        for deal in result.deals:
            assert deal.discount_percent >= 80.0

    @pytest.mark.asyncio
    async def test_sorted_by_absolute_savings(
        self,
        cache: InMemoryCache,
        mock_providers: list[AsyncMock],
    ) -> None:
        """Verify deals are sorted by absolute savings descending."""
        service = DiscountService(mock_providers, cache, discount_threshold=80.0)
        result = await service.get_crazy_discounts(limit=10)

        savings = [(d.original_price or 0) - d.current_price for d in result.deals]
        assert savings == sorted(savings, reverse=True)

    @pytest.mark.asyncio
    async def test_empty_week(
        self,
        cache: InMemoryCache,
    ) -> None:
        """Verify empty result when no provider has deals above threshold."""
        p = AsyncMock()
        p.name = "empty"
        p.get_deals.return_value = ProviderResult(
            deals=[
                _deal(
                    id="low",
                    title="Low Discount",
                    discount_percent=10.0,
                    current_price=45.0,
                    original_price=50.0,
                    provider_name="empty",
                ),
            ],
            metadata=ProviderMetadata(provider="empty", returned=1),
        )

        service = DiscountService([p], cache, discount_threshold=80.0)
        result = await service.get_crazy_discounts(limit=10)

        assert result.total == 0
        assert len(result.deals) == 0

    @pytest.mark.asyncio
    async def test_provider_failure_isolation(
        self,
        cache: InMemoryCache,
    ) -> None:
        """Verify one failing provider doesn't block results."""
        p1 = AsyncMock()
        p1.name = "good"
        p1.get_deals.return_value = ProviderResult(
            deals=[
                _deal(
                    id="g1",
                    title="Good Deal",
                    discount_percent=90.0,
                    current_price=5.0,
                    original_price=50.0,
                    store_url=STEAM_APP_99,
                    provider_name="good",
                ),
            ],
            metadata=ProviderMetadata(provider="good", returned=1),
        )
        p2 = AsyncMock()
        p2.name = "broken"
        p2.get_deals.side_effect = ValueError("Boom")

        service = DiscountService([p1, p2], cache, discount_threshold=80.0)
        result = await service.get_crazy_discounts(limit=10)

        assert result.total == 1
        assert len(result.errors) >= 1

    @pytest.mark.asyncio
    async def test_crazy_discounts_limit_applied(
        self,
        cache: InMemoryCache,
        mock_providers: list[AsyncMock],
    ) -> None:
        """Verify limit restricts the number of returned deals."""
        service = DiscountService(mock_providers, cache, discount_threshold=80.0)
        result = await service.get_crazy_discounts(limit=2)

        assert len(result.deals) <= 2


@pytest.mark.unit
class TestDiscountServiceGenreDeals:
    """get_genre_deals() behavior."""

    @pytest.mark.asyncio
    async def test_genre_filter_match(
        self,
        cache: InMemoryCache,
    ) -> None:
        """Verify deals matching favorite genres are returned."""
        p = AsyncMock()
        p.name = "test"
        p.get_deals.return_value = ProviderResult(
            deals=[
                _deal(
                    id="a1",
                    title="RPG Adventure",
                    discount_percent=90.0,
                    current_price=5.0,
                    original_price=50.0,
                    store_url=STEAM_APP_10,
                    provider_name="test",
                    raw_metadata={"genres": ["RPG"]},
                ),
                _deal(
                    id="b1",
                    title="Strategy Game",
                    discount_percent=85.0,
                    current_price=7.0,
                    original_price=50.0,
                    store_url=STEAM_APP_11,
                    provider_name="test",
                    raw_metadata={"genres": ["Strategy"]},
                ),
                _deal(
                    id="c1",
                    title="No Genre Match",
                    discount_percent=90.0,
                    current_price=3.0,
                    original_price=30.0,
                    store_url=STEAM_APP_12,
                    provider_name="test",
                    raw_metadata={"genres": ["Simulation"]},
                ),
            ],
            metadata=ProviderMetadata(provider="test", returned=3),
        )

        service = DiscountService(
            [p],
            cache,
            favorite_genres=["RPG", "Action"],
            discount_threshold=80.0,
        )
        result = await service.get_genre_deals(limit=10)

        assert result.total == 1
        assert result.deals[0].title == "RPG Adventure"

    @pytest.mark.asyncio
    async def test_genre_filter_fallback_to_title(
        self,
        cache: InMemoryCache,
    ) -> None:
        """Verify fallback matching by title when no genre metadata exists."""
        p = AsyncMock()
        p.name = "test"
        p.get_deals.return_value = ProviderResult(
            deals=[
                _deal(
                    id="a1",
                    title="Roguelike Dungeon Crawler",
                    discount_percent=90.0,
                    current_price=5.0,
                    original_price=50.0,
                    store_url=STEAM_APP_20,
                    provider_name="test",
                ),
            ],
            metadata=ProviderMetadata(provider="test", returned=1),
        )

        service = DiscountService(
            [p],
            cache,
            favorite_genres=["roguelike"],
            discount_threshold=80.0,
        )
        result = await service.get_genre_deals(limit=10)

        assert result.total == 1

    @pytest.mark.asyncio
    async def test_empty_favorite_genres_returns_empty(
        self,
        cache: InMemoryCache,
    ) -> None:
        """Verify get_genre_deals returns empty when no favorite genres set."""
        service = DiscountService(
            [],
            cache,
            favorite_genres=[],
            discount_threshold=80.0,
        )
        result = await service.get_genre_deals(limit=10)

        assert result.total == 0
        assert len(result.deals) == 0


@pytest.mark.unit
class TestDiscountServiceMerge:
    """Deal merging and deduplication."""

    def test_merge_same_store_url_deduplicates(self) -> None:
        """Verify same store_url from two providers yields one Deal."""
        deals = [
            _deal(
                id="a",
                title="Same Game",
                discount_percent=80.0,
                store_url=STEAM_APP_100,
                provider_name="cheapshark",
            ),
            _deal(
                id="b",
                title="Same Game",
                discount_percent=85.0,
                store_url=STEAM_APP_100,
                provider_name="epic",
            ),
        ]
        merged = DiscountService._merge_deals(deals)
        assert len(merged) == 1
        assert sorted(merged[0].provider_names) == ["cheapshark", "epic"]

    def test_merge_keeps_best_discount(self) -> None:
        """Verify merged deal keeps the higher discount_percent."""
        deals = [
            _deal(
                id="a",
                title="Same Game",
                discount_percent=80.0,
                current_price=10.0,
                store_url=STEAM_APP_200,
                provider_name="cheapshark",
            ),
            _deal(
                id="b",
                title="Same Game",
                discount_percent=90.0,
                current_price=5.0,
                store_url=STEAM_APP_200,
                provider_name="epic",
            ),
        ]
        merged = DiscountService._merge_deals(deals)
        assert len(merged) == 1
        assert merged[0].discount_percent == 90.0
        assert merged[0].current_price == 5.0

    def test_merge_preserves_distinct_deals(self) -> None:
        """Verify different store_urls are not merged."""
        deals = [
            _deal(
                id="a",
                title="Game A",
                store_url=STEAM_APP_301,
                provider_name="cheapshark",
            ),
            _deal(
                id="b",
                title="Game B",
                store_url=EPIC_GAMEB_URL,
                provider_name="epic",
            ),
        ]
        merged = DiscountService._merge_deals(deals)
        assert len(merged) == 2

    def test_merge_fallback_key_when_no_store_url(self) -> None:
        """Verify fallback dedup key when store_url is None."""
        deals = [
            _deal(
                id="a",
                title="Same Title",
                store=StoreName.Steam,
                store_url=None,
                provider_name="cheapshark",
            ),
            _deal(
                id="b",
                title="Same Title",
                store=StoreName.Steam,
                store_url=None,
                provider_name="epic",
            ),
        ]
        merged = DiscountService._merge_deals(deals)
        assert len(merged) == 1
        assert sorted(merged[0].provider_names) == ["cheapshark", "epic"]


@pytest.mark.unit
class TestDiscountServiceHistoricalLow:
    """enrich_with_historical_low() behavior."""

    @pytest.mark.asyncio
    async def test_enrich_itad_deal(
        self,
        cache: InMemoryCache,
    ) -> None:
        """Verify ITAD deal with itad_plain_id gets historical low data."""
        itad = AsyncMock()
        itad.name = "isthereanydeal"
        itad.get_deals.return_value = ProviderResult(
            metadata=ProviderMetadata(provider="isthereanydeal", returned=0),
        )
        itad.get_lowest_price.return_value = {
            "lowest_price": 3.99,
            "lowest_recorded_date": "2025-06-01",
        }

        service = DiscountService([itad], cache, discount_threshold=80.0)
        deal = _deal(
            id="test",
            title="Test Deal",
            current_price=9.99,
            original_price=59.99,
            discount_percent=83.0,
            store_url=STEAM_APP_500,
            provider_name="isthereanydeal",
            raw_metadata={"itad_plain_id": "test_deal_1"},
        )
        enriched = await service.enrich_with_historical_low(deal)

        assert enriched.raw_metadata.get("historical_low") == 3.99
        assert enriched.raw_metadata.get("historical_low_date") == "2025-06-01"

    @pytest.mark.asyncio
    async def test_enrich_no_itad_provider(
        self,
        cache: InMemoryCache,
    ) -> None:
        """Verify deal is returned unchanged when no ITAD provider."""
        service = DiscountService([], cache, discount_threshold=80.0)
        deal = _deal(
            id="test",
            title="Test Deal",
            current_price=9.99,
            provider_name="test",
        )
        enriched = await service.enrich_with_historical_low(deal)

        assert enriched is deal

    @pytest.mark.asyncio
    async def test_enrich_no_plain_id(
        self,
        cache: InMemoryCache,
    ) -> None:
        """Verify deal is returned unchanged when no itad_plain_id."""
        itad = AsyncMock()
        itad.name = "isthereanydeal"
        itad.get_lowest_price = AsyncMock()

        service = DiscountService([itad], cache, discount_threshold=80.0)
        deal = _deal(
            id="test",
            title="Test Deal",
            current_price=9.99,
            provider_name="test",
        )
        enriched = await service.enrich_with_historical_low(deal)

        assert enriched is deal
        itad.get_lowest_price.assert_not_called()

    @pytest.mark.asyncio
    async def test_enrich_lowest_price_none(
        self,
        cache: InMemoryCache,
    ) -> None:
        """Verify deal is unchanged when ITAD returns no lowest price."""
        itad = AsyncMock()
        itad.name = "isthereanydeal"
        itad.get_lowest_price.return_value = None

        service = DiscountService([itad], cache, discount_threshold=80.0)
        deal = _deal(
            id="test",
            title="Test Deal",
            current_price=9.99,
            raw_metadata={"itad_plain_id": "test_deal_1"},
        )
        enriched = await service.enrich_with_historical_low(deal)

        assert enriched is deal


@pytest.mark.unit
class TestDiscountServiceMatchesFavoriteGenres:
    """_matches_favorite_genres() behavior."""

    def test_match_by_genre_list(self) -> None:
        """Verify deal with matching genre in raw_metadata returns True."""
        service = DiscountService([], InMemoryCache(), favorite_genres=["RPG"])
        deal = _deal(raw_metadata={"genres": ["RPG", "Action"]})
        assert service._matches_favorite_genres(deal) is True

    def test_match_by_title_fallback(self) -> None:
        """Verify deal with matching keyword in title returns True."""
        service = DiscountService([], InMemoryCache(), favorite_genres=["roguelike"])
        deal = _deal(title="Roguelike Dungeon Crawler")
        assert service._matches_favorite_genres(deal) is True

    def test_no_match(self) -> None:
        """Verify deal with no matching genre returns False."""
        service = DiscountService([], InMemoryCache(), favorite_genres=["RPG"])
        deal = _deal(
            title="Strategy Game",
            raw_metadata={"genres": ["Strategy"]},
        )
        assert service._matches_favorite_genres(deal) is False

    def test_empty_favorite_genres(self) -> None:
        """Verify all deals match when no favorite genres."""
        service = DiscountService([], InMemoryCache(), favorite_genres=[])
        deal = _deal(title="Anything")
        assert service._matches_favorite_genres(deal) is True
