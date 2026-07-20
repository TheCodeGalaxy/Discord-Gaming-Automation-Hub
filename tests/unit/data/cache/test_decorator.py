"""Unit tests for CachedProviderDecorator."""
# ruff: noqa: PLR2004 — test assertions use literal magic values for clarity

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from gaming_hub.data.cache.decorator import CachedProviderDecorator
from gaming_hub.data.cache.in_memory import InMemoryCache
from gaming_hub.models.dto.provider import ProviderMetadata, ProviderResult
from gaming_hub.models.dto.request import SearchRequest


@pytest.fixture()
def cache() -> InMemoryCache:
    """Return a cache with default 60s TTL for decorator tests."""
    return InMemoryCache(default_ttl=60)


@pytest.fixture()
def mock_provider() -> AsyncMock:
    """Return a mocked DataProvider with canned ProviderResult values."""
    provider = AsyncMock()
    provider.name = "test_provider"
    provider.search.return_value = ProviderResult(
        games=[],
        metadata=ProviderMetadata(provider="test_provider", returned=0),
    )
    provider.get_deals.return_value = ProviderResult(
        deals=[],
        metadata=ProviderMetadata(provider="test_provider", returned=0),
    )
    provider.get_free_games.return_value = ProviderResult(
        games=[],
        metadata=ProviderMetadata(provider="test_provider", returned=0),
    )
    provider.healthcheck.return_value = {"available": True}
    return provider


@pytest.mark.unit
class TestCachedProviderDecorator:
    """Decorator caching behavior."""

    @pytest.mark.asyncio
    async def test_search_calls_provider_on_miss(
        self, cache: InMemoryCache, mock_provider: AsyncMock,
    ) -> None:
        """Verify provider.search() is called on first cache miss."""
        decorator = CachedProviderDecorator(mock_provider, cache)
        request = SearchRequest(query="cyberpunk")

        result = await decorator.search(request)

        mock_provider.search.assert_awaited_once()
        assert result.metadata.provider == "test_provider"

    @pytest.mark.asyncio
    async def test_search_returns_cached_on_hit(
        self, cache: InMemoryCache, mock_provider: AsyncMock,
    ) -> None:
        """Verify cached search result is returned on subsequent calls."""
        decorator = CachedProviderDecorator(mock_provider, cache)
        request = SearchRequest(query="cyberpunk")

        await decorator.search(request)
        result2 = await decorator.search(request)

        assert mock_provider.search.call_count == 1
        assert result2.metadata.provider == "test_provider"

    @pytest.mark.asyncio
    async def test_get_deals_calls_provider_on_miss(
        self, cache: InMemoryCache, mock_provider: AsyncMock,
    ) -> None:
        """Verify provider.get_deals() is called on first miss."""
        decorator = CachedProviderDecorator(mock_provider, cache)

        await decorator.get_deals(limit=5)

        mock_provider.get_deals.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_deals_returns_cached_on_hit(
        self, cache: InMemoryCache, mock_provider: AsyncMock,
    ) -> None:
        """Verify cached deals result is returned on subsequent calls."""
        decorator = CachedProviderDecorator(mock_provider, cache)

        await decorator.get_deals(limit=5)
        await decorator.get_deals(limit=5)

        assert mock_provider.get_deals.call_count == 1

    @pytest.mark.asyncio
    async def test_get_free_games_calls_provider_on_miss(
        self, cache: InMemoryCache, mock_provider: AsyncMock,
    ) -> None:
        """Verify provider.get_free_games() is called on first miss."""
        decorator = CachedProviderDecorator(mock_provider, cache)

        await decorator.get_free_games(upcoming=False)

        mock_provider.get_free_games.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_free_games_returns_cached_on_hit(
        self, cache: InMemoryCache, mock_provider: AsyncMock,
    ) -> None:
        """Verify cached free_games result is returned on subsequent calls."""
        decorator = CachedProviderDecorator(mock_provider, cache)

        await decorator.get_free_games(upcoming=False)
        await decorator.get_free_games(upcoming=False)

        assert mock_provider.get_free_games.call_count == 1

    @pytest.mark.asyncio
    async def test_healthcheck_not_cached(
        self, cache: InMemoryCache, mock_provider: AsyncMock,
    ) -> None:
        """Verify healthcheck bypasses cache and always calls the provider."""
        decorator = CachedProviderDecorator(mock_provider, cache)

        await decorator.healthcheck()
        await decorator.healthcheck()

        assert mock_provider.healthcheck.call_count == 2

    @pytest.mark.asyncio
    async def test_name_delegated(self, mock_provider: AsyncMock) -> None:
        """Verify decorator.name delegates to wrapped provider.name."""
        cache = InMemoryCache()
        decorator = CachedProviderDecorator(mock_provider, cache)
        assert decorator.name == "test_provider"

    @pytest.mark.asyncio
    async def test_different_params_different_cache_keys(
        self, cache: InMemoryCache, mock_provider: AsyncMock,
    ) -> None:
        """Verify different search params produce separate cache entries."""
        decorator = CachedProviderDecorator(mock_provider, cache)

        await decorator.search(SearchRequest(query="cyberpunk"))
        await decorator.search(SearchRequest(query="hades"))

        assert mock_provider.search.call_count == 2
