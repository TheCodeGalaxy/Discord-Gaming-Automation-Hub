"""Unit tests for SearchService."""
# ruff: noqa: PLR2004 — test assertions use literal magic values for clarity

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from gaming_hub.core.exceptions import ProviderError, ProviderRateLimitError
from gaming_hub.data.cache.in_memory import InMemoryCache
from gaming_hub.models.domain.deal import Deal
from gaming_hub.models.domain.game import Game
from gaming_hub.models.dto.provider import ProviderMetadata, ProviderResult
from gaming_hub.models.dto.request import SearchRequest
from gaming_hub.services.search_service import AutocompleteItem, SearchService


@pytest.fixture()
def cache() -> InMemoryCache:
    """Return a fresh in-memory cache for service-level caching."""
    return InMemoryCache(default_ttl=60)


@pytest.fixture()
def mock_providers() -> list[AsyncMock]:
    """Return 2 mocked providers with canned search results."""
    p1 = AsyncMock()
    p1.name = "provider_a"
    p1.search.return_value = ProviderResult(
        games=[
            Game(id="1", title="Cyberpunk 2077", steam_app_id=1091500, provider_name="provider_a"),
            Game(id="2", title="Hades", steam_app_id=1145360, provider_name="provider_a"),
        ],
        metadata=ProviderMetadata(provider="provider_a", returned=2),
    )

    p2 = AsyncMock()
    p2.name = "provider_b"
    p2.search.return_value = ProviderResult(
        games=[
            Game(id="3", title="Elden Ring", steam_app_id=1245620, provider_name="provider_b"),
            Game(id="4", title="Baldur's Gate 3", steam_app_id=1086940, provider_name="provider_b"),
        ],
        deals=[
            Deal(
            id="d1",
            title="Elden Ring",
            current_price=39.99,
            original_price=59.99,
            discount_percent=33.33,
            provider_names=["provider_b"],
        ),
        ],
        metadata=ProviderMetadata(provider="provider_b", returned=2),
    )
    return [p1, p2]


@pytest.mark.unit
class TestSearchService:
    """Core search orchestration."""

    @pytest.mark.asyncio
    async def test_search_aggregates_all_providers(
        self, cache: InMemoryCache, mock_providers: list[AsyncMock],
    ) -> None:
        """Verify search collects games and deals from all providers."""
        service = SearchService(mock_providers, cache)
        request = SearchRequest(query="test", limit=10)
        result = await service.search(request)

        assert len(result.games) == 4
        assert len(result.deals) == 1
        assert result.total_games == 4
        assert result.total_deals == 1
        assert result.took_ms >= 0

    @pytest.mark.asyncio
    async def test_search_deduplicates_by_steam_app_id(
        self, cache: InMemoryCache,
    ) -> None:
        """Verify games with same steam_app_id are deduplicated."""
        p1 = AsyncMock()
        p1.name = "p1"
        p1.search.return_value = ProviderResult(
            games=[Game(id="1", title="Cyberpunk 2077", steam_app_id=1091500, provider_name="p1")],
            metadata=ProviderMetadata(provider="p1", returned=1),
        )
        p2 = AsyncMock()
        p2.name = "p2"
        p2.search.return_value = ProviderResult(
            games=[Game(id="2", title="Cyberpunk 2077", steam_app_id=1091500, provider_name="p2")],
            metadata=ProviderMetadata(provider="p2", returned=1),
        )

        service = SearchService([p1, p2], cache)
        result = await service.search(SearchRequest(query="cyberpunk", limit=10))

        assert len(result.games) == 1  # deduplicated
        assert result.games[0].provider_name == "p1"  # first wins

    @pytest.mark.asyncio
    async def test_search_deduplicates_by_normalized_title(
        self, cache: InMemoryCache,
    ) -> None:
        """Verify games with different IDs but same normalized title are merged."""
        p1 = AsyncMock()
        p1.name = "p1"
        p1.search.return_value = ProviderResult(
            games=[Game(id="epic-1", title="Cyberpunk 2077", provider_name="p1")],
            metadata=ProviderMetadata(provider="p1", returned=1),
        )
        p2 = AsyncMock()
        p2.name = "p2"
        p2.search.return_value = ProviderResult(
            games=[Game(id="gog-1", title="Cyberpunk 2077", provider_name="p2")],
            metadata=ProviderMetadata(provider="p2", returned=1),
        )

        service = SearchService([p1, p2], cache)
        result = await service.search(SearchRequest(query="cyberpunk", limit=10))

        assert len(result.games) == 1  # deduplicated by normalized title

    @pytest.mark.asyncio
    async def test_search_ranking_exact_match_first(
        self, cache: InMemoryCache,
    ) -> None:
        """Verify exact title match ranks above partial match."""
        p1 = AsyncMock()
        p1.name = "p1"
        p1.search.return_value = ProviderResult(
            games=[
                Game(id="1", title="Hades II", steam_app_id=999, provider_name="p1"),
                Game(id="2", title="Hades", steam_app_id=111, provider_name="p1"),
            ],
            metadata=ProviderMetadata(provider="p1", returned=2),
        )

        service = SearchService([p1], cache)
        result = await service.search(SearchRequest(query="Hades", limit=10))

        assert len(result.games) == 2
        assert result.games[0].title == "Hades"  # exact match first
        assert result.games[1].title == "Hades II"  # partial match second

    @pytest.mark.asyncio
    async def test_search_error_isolation_rate_limit(
        self, cache: InMemoryCache,
    ) -> None:
        """Verify a rate-limited provider does not block other results."""
        p1 = AsyncMock()
        p1.name = "fast_provider"
        p1.search.return_value = ProviderResult(
            games=[
                Game(
                    id="1", title="Cyberpunk 2077", steam_app_id=1091500,
                    provider_name="fast_provider",
                ),
            ],
            metadata=ProviderMetadata(provider="fast_provider", returned=1),
        )
        p2 = AsyncMock()
        p2.name = "rate_limited"
        p2.search.side_effect = ProviderRateLimitError("Too many requests", provider="rate_limited")

        service = SearchService([p1, p2], cache)
        result = await service.search(SearchRequest(query="cyberpunk", limit=10))

        assert len(result.games) == 1  # fast_provider still returns
        assert len(result.errors) == 1
        assert result.errors[0]["type"] == "rate_limit"
        assert result.errors[0]["provider"] == "rate_limited"

    @pytest.mark.asyncio
    async def test_search_error_isolation_provider_error(
        self, cache: InMemoryCache,
    ) -> None:
        """Verify a provider error does not block other results."""
        p1 = AsyncMock()
        p1.name = "good"
        p1.search.return_value = ProviderResult(
            games=[
                Game(id="1", title="Cyberpunk 2077", steam_app_id=1091500, provider_name="good"),
            ],
            metadata=ProviderMetadata(provider="good", returned=1),
        )
        p2 = AsyncMock()
        p2.name = "broken"
        p2.search.side_effect = ProviderError("Internal failure", provider="broken")

        service = SearchService([p1, p2], cache)
        result = await service.search(SearchRequest(query="cyberpunk", limit=10))

        assert len(result.games) == 1
        assert len(result.errors) == 1
        assert result.errors[0]["type"] == "provider_error"

    @pytest.mark.asyncio
    async def test_search_error_isolation_unexpected(
        self, cache: InMemoryCache,
    ) -> None:
        """Verify an unexpected exception from a provider is caught."""
        p1 = AsyncMock()
        p1.name = "good"
        p1.search.return_value = ProviderResult(
            games=[
                Game(id="1", title="Cyberpunk 2077", steam_app_id=1091500, provider_name="good"),
            ],
            metadata=ProviderMetadata(provider="good", returned=1),
        )
        p2 = AsyncMock()
        p2.name = "exploder"
        p2.search.side_effect = ValueError("Something went wrong")

        service = SearchService([p1, p2], cache)
        result = await service.search(SearchRequest(query="cyberpunk", limit=10))

        assert len(result.games) == 1
        assert len(result.errors) == 1
        assert result.errors[0]["type"] == "unexpected"


@pytest.mark.unit
class TestSearchServiceAutocomplete:
    """Autocomplete suggestion behavior."""

    @pytest.mark.asyncio
    async def test_autocomplete_returns_items(
        self, cache: InMemoryCache, mock_providers: list[AsyncMock],
    ) -> None:
        """Verify autocomplete returns properly shaped items."""
        service = SearchService(mock_providers, cache)
        items = await service.autocomplete("cyber", limit=3)

        assert len(items) <= 3
        for item in items:
            assert isinstance(item, AutocompleteItem)
            assert item.label
            assert item.value
            assert item.provider

    @pytest.mark.asyncio
    async def test_autocomplete_respects_limit(
        self, cache: InMemoryCache, mock_providers: list[AsyncMock],
    ) -> None:
        """Verify autocomplete returns at most ``limit`` items."""
        service = SearchService(mock_providers, cache)
        items = await service.autocomplete("", limit=1)

        assert len(items) <= 1

    @pytest.mark.asyncio
    async def test_autocomplete_items_have_correct_fields(
        self, cache: InMemoryCache,
    ) -> None:
        """Verify autocomplete items contain label, value, and provider."""
        p = AsyncMock()
        p.name = "test_provider"
        p.search.return_value = ProviderResult(
            games=[
                Game(id="42", title="Test Game", steam_app_id=12345, provider_name="test_provider"),
            ],
            metadata=ProviderMetadata(provider="test_provider", returned=1),
        )

        service = SearchService([p], cache)
        items = await service.autocomplete("test", limit=5)

        assert len(items) == 1
        assert items[0].label == "Test Game"
        assert items[0].value == "12345"
        assert items[0].provider == "test_provider"


@pytest.mark.unit
class TestSearchServiceHelpers:
    """Normalization, merging, and ranking helpers."""

    def test_normalize_title_removes_punctuation(self) -> None:
        """Verify _normalize_title strips punctuation and lowercases."""
        result = SearchService._normalize_title("Baldur's Gate 3!")
        assert result == "baldursgate3"

    def test_normalize_title_handles_whitespace(self) -> None:
        """Verify _normalize_title strips surrounding whitespace."""
        result = SearchService._normalize_title("  Cyberpunk 2077  ")
        assert result == "cyberpunk2077"

    def test_normalize_title_empty_string(self) -> None:
        """Verify _normalize_title handles empty input."""
        assert SearchService._normalize_title("") == ""

    def test_normalize_title_already_clean(self) -> None:
        """Verify _normalize_title is idempotent for clean strings."""
        result = SearchService._normalize_title("hades")
        assert result == "hades"

    def test_merge_games_deduplicates(self) -> None:
        """Verify _merge_games removes duplicates by steam_app_id."""
        games = [
            Game(id="1", title="Cyberpunk", steam_app_id=100, provider_name="a"),
            Game(id="2", title="Cyberpunk", steam_app_id=100, provider_name="b"),
        ]
        merged = SearchService._merge_games(games)
        assert len(merged) == 1

    def test_merge_games_deduplicates_by_title_fallback(self) -> None:
        """Verify _merge_games falls back to title dedup when steam_app_id is missing."""
        games = [
            Game(id="epic-1", title="Cyberpunk 2077", provider_name="epic"),
            Game(id="gog-1", title="Cyberpunk 2077", provider_name="gog"),
        ]
        merged = SearchService._merge_games(games)
        assert len(merged) == 1

    def test_merge_games_preserves_distinct_titles(self) -> None:
        """Verify _merge_games keeps games with different titles."""
        games = [
            Game(id="1", title="Cyberpunk 2077", steam_app_id=100, provider_name="a"),
            Game(id="2", title="Hades", steam_app_id=200, provider_name="a"),
        ]
        merged = SearchService._merge_games(games)
        assert len(merged) == 2

    def test_merge_deals_deduplicates_by_id(self) -> None:
        """Verify _merge_deals removes duplicate deal IDs."""
        deals = [
            Deal(id="d1", title="Deal A", current_price=10.0, provider_names=["a"]),
            Deal(id="d1", title="Deal A", current_price=10.0, provider_names=["b"]),
        ]
        merged = SearchService._merge_deals(deals)
        assert len(merged) == 1

    def test_merge_deals_preserves_distinct_deals(self) -> None:
        """Verify _merge_deals keeps deals with different IDs."""
        deals = [
            Deal(id="d1", title="Deal A", current_price=10.0, provider_names=["a"]),
            Deal(id="d2", title="Deal B", current_price=20.0, provider_names=["a"]),
        ]
        merged = SearchService._merge_deals(deals)
        assert len(merged) == 2

    def test_rank_results_exact_match_first(self) -> None:
        """Verify exact title match scores above partial match."""
        games = [
            Game(id="1", title="Hades II", steam_app_id=200, provider_name="a"),
            Game(id="2", title="Hades", steam_app_id=100, provider_name="a"),
        ]
        request = SearchRequest(query="Hades")
        ranked = SearchService._rank_results(games, request)
        assert ranked[0].title == "Hades"
        assert ranked[1].title == "Hades II"

    def test_rank_results_steam_app_id_bonus(self) -> None:
        """Verify games with steam_app_id rank higher."""
        games = [
            Game(id="epic-1", title="Cyberpunk 2077", provider_name="epic"),
            Game(id="steam-1", title="Cyberpunk 2077", steam_app_id=1091500, provider_name="steam"),
        ]
        request = SearchRequest(query="Cyberpunk")
        ranked = SearchService._rank_results(games, request)
        assert ranked[0].title == "Cyberpunk 2077"
        assert ranked[0].steam_app_id == 1091500  # steam version first

    def test_rank_deals_by_discount(self) -> None:
        """Verify deals are sorted by discount_percent descending."""
        deals = [
            Deal(
                id="d1", title="Small", current_price=45.0, original_price=50.0,
                discount_percent=10.0, provider_names=["a"],
            ),
            Deal(
                id="d2", title="Big", current_price=10.0, original_price=100.0,
                discount_percent=90.0, provider_names=["a"],
            ),
        ]
        ranked = SearchService._rank_deals(deals)
        assert ranked[0].title == "Big"
        assert ranked[1].title == "Small"
