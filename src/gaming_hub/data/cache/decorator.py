"""Cached provider decorator.

Wraps a ``DataProvider`` instance and caches its results transparently.
Services interact with the decorator as if it were the provider itself.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from gaming_hub.data.cache.key import make_cache_key
from gaming_hub.models.dto.provider import ProviderMetadata, ProviderResult

if TYPE_CHECKING:
    from gaming_hub.core.interfaces import CacheBackend, DataProvider
    from gaming_hub.models.dto.request import SearchRequest


class CachedProviderDecorator:
    """Decorator that adds caching to a DataProvider."""

    def __init__(self, provider: DataProvider, cache: CacheBackend) -> None:
        """Wrap a provider with cache transparently."""
        self._provider = provider
        self._cache = cache

    @property
    def name(self) -> str:
        """Delegate name to the underlying provider."""
        return self._provider.name

    async def search(self, request: SearchRequest) -> ProviderResult:
        """Search with caching."""
        key = make_cache_key(
            self._provider.name,
            "search",
            query=request.query,
            limit=request.limit,
            exact=request.exact or None,
            steam_app_id=request.steam_app_id,
        )
        cached: ProviderResult | None = cast(
            "ProviderResult | None", await self._cache.get(key),
        )
        if cached is not None:
            return cached
        result = await self._provider.search(request)
        await self._cache.set(key, result, ttl=600)
        return result

    async def get_free_games(self, *, upcoming: bool = False) -> ProviderResult:
        """Get free games with caching."""
        key = make_cache_key(
            self._provider.name,
            "free_games",
            upcoming=upcoming or None,
        )
        cached: ProviderResult | None = cast(
            "ProviderResult | None", await self._cache.get(key),
        )
        if cached is not None:
            return cached
        result = await self._provider.get_free_games(upcoming=upcoming)
        ttl = 900 if self._provider.name == "epic" else 600
        await self._cache.set(key, result, ttl=ttl)
        return result

    async def get_deals(self, *, limit: int = 10) -> ProviderResult:
        """Get deals with caching."""
        key = make_cache_key(
            self._provider.name,
            "deals",
            limit=limit,
        )
        cached: ProviderResult | None = cast(
            "ProviderResult | None", await self._cache.get(key),
        )
        if cached is not None:
            return cached
        result = await self._provider.get_deals(limit=limit)
        ttl = 300  # deals are volatile
        await self._cache.set(key, result, ttl=ttl)
        return result

    async def get_new_releases(self, *, days_ahead: int = 30, limit: int = 20) -> ProviderResult:
        """Get new releases with caching."""
        if not hasattr(type(self._provider), "get_new_releases"):
            return ProviderResult(metadata=ProviderMetadata(provider=self._provider.name))
        key = make_cache_key(
            self._provider.name,
            "new_releases",
            days_ahead=days_ahead,
            limit=limit,
        )
        cached: ProviderResult | None = cast(
            "ProviderResult | None", await self._cache.get(key),
        )
        if cached is not None:
            return cached
        result = await self._provider.get_new_releases(days_ahead=days_ahead, limit=limit)  # type: ignore[attr-defined]
        ttl = 600
        await self._cache.set(key, result, ttl=ttl)
        return cast("ProviderResult", result)

    async def get_monthly_releases(
        self, year: int, month: int, *, limit: int = 10,
    ) -> ProviderResult:
        """Get monthly releases with caching."""
        if not hasattr(type(self._provider), "get_monthly_releases"):
            return ProviderResult(metadata=ProviderMetadata(provider=self._provider.name))
        key = make_cache_key(
            self._provider.name,
            "monthly_releases",
            year=year,
            month=month,
            limit=limit,
        )
        cached: ProviderResult | None = cast(
            "ProviderResult | None", await self._cache.get(key),
        )
        if cached is not None:
            return cached
        result = await self._provider.get_monthly_releases(year, month, limit=limit)  # type: ignore[attr-defined]
        await self._cache.set(key, result, ttl=600)
        return cast("ProviderResult", result)

    async def get_featured_releases(
        self, year: int, month: int, *, limit: int = 20,
    ) -> ProviderResult:
        """Get featured releases with caching."""
        if not hasattr(type(self._provider), "get_featured_releases"):
            return ProviderResult(metadata=ProviderMetadata(provider=self._provider.name))
        key = make_cache_key(
            self._provider.name,
            "featured_releases",
            year=year,
            month=month,
            limit=limit,
        )
        cached: ProviderResult | None = cast(
            "ProviderResult | None", await self._cache.get(key),
        )
        if cached is not None:
            return cached
        result = await self._provider.get_featured_releases(year, month, limit=limit)  # type: ignore[attr-defined]
        await self._cache.set(key, result, ttl=600)
        return cast("ProviderResult", result)

    async def get_upcoming_releases(
        self, year: int, month: int, *, limit: int = 20,
    ) -> ProviderResult:
        """Get upcoming releases with caching."""
        if not hasattr(type(self._provider), "get_upcoming_releases"):
            return ProviderResult(metadata=ProviderMetadata(provider=self._provider.name))
        key = make_cache_key(
            self._provider.name,
            "upcoming_releases",
            year=year,
            month=month,
            limit=limit,
        )
        cached: ProviderResult | None = cast(
            "ProviderResult | None", await self._cache.get(key),
        )
        if cached is not None:
            return cached
        result = await self._provider.get_upcoming_releases(year, month, limit=limit)  # type: ignore[attr-defined]
        await self._cache.set(key, result, ttl=600)
        return cast("ProviderResult", result)

    async def healthcheck(self) -> dict[str, Any]:
        """Healthcheck — not cached (always live)."""
        return await self._provider.healthcheck()

    async def get_search_releases(
        self,
        page_range: tuple[int, int],
        *,
        step: int = 3,
    ) -> ProviderResult:
        """Steam search — daily data, not cached."""
        return await self._provider.get_search_releases(page_range, step=step)

    async def get_trending(self, *, limit: int = 40) -> ProviderResult:
        """Get trending games — not cached (volatile)."""
        if not hasattr(type(self._provider), "get_trending"):
            return ProviderResult(metadata=ProviderMetadata(provider=self._provider.name))
        return await self._provider.get_trending(limit=limit)  # type: ignore[attr-defined]
