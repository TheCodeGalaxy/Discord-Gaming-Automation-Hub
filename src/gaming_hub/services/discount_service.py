"""Discount service — discover, filter, and rank game deals across all providers.

Aggregates deals from all registered providers, filters by discount threshold
and genre preferences, detects historical-low prices, and produces the data
payloads for the ``#crazy-discounts`` and ``#top-this-week`` Discord channels.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, cast

from gaming_hub.data.cache.decorator import CachedProviderDecorator
from gaming_hub.models.dto.provider import ProviderMetadata, ProviderResult

if TYPE_CHECKING:
    from gaming_hub.core.interfaces import CacheBackend, DataProvider
    from gaming_hub.models.domain.deal import Deal

logger = logging.getLogger(__name__)


@dataclass
class DiscountResult:
    """Aggregated discount result from all providers."""

    deals: list[Any] = field(default_factory=list)
    total: int = 0
    threshold: float = 80.0
    errors: list[dict[str, Any]] = field(default_factory=list)
    fetched_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class DiscountService:
    """Orchestrate deal aggregation, filtering, and ranking across providers.

    Attributes:
        _providers: Cached provider decorators used for deal fetching.
        _itad_provider: Raw ITAD provider for historical low enrichment.
        _favorite_genres: Genre keywords used for genre-based filtering.
        _discount_threshold: Minimum discount percentage for ``get_crazy_discounts``.
    """

    def __init__(
        self,
        providers: list[DataProvider],
        cache: CacheBackend,
        favorite_genres: list[str] | None = None,
        discount_threshold: float = 80.0,
    ) -> None:
        """Wrap each provider with caching and store internally.

        Args:
            providers: List of ``DataProvider`` instances (raw, not wrapped).
            cache: ``CacheBackend`` instance shared across all providers.
            favorite_genres: Genre keywords for genre-based filtering.
            discount_threshold: Minimum discount percentage (0-100).
        """
        self._providers = [CachedProviderDecorator(p, cache) for p in providers]
        self._itad_provider = next(
            (p for p in providers if getattr(p, "name", "") == "isthereanydeal"),
            None,
        )
        self._favorite_genres = favorite_genres or []
        self._discount_threshold = discount_threshold

    async def get_crazy_discounts(self, *, limit: int = 20) -> DiscountResult:
        """Return deals with discount >= threshold, sorted by absolute savings.

        Args:
            limit: Maximum number of deals to return.

        Returns:
            A ``DiscountResult`` with filtered, sorted deals.
        """
        tasks = [self._safe_get_deals(provider, limit=limit) for provider in self._providers]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        all_deals: list[Deal] = []
        errors: list[dict[str, Any]] = []

        for provider, result in zip(self._providers, results, strict=False):
            if isinstance(result, Exception):
                errors.append({"provider": provider.name, "error": str(result)})
                continue
            assert isinstance(result, ProviderResult)
            all_deals.extend(result.deals or [])
            if result.metadata.errors:
                errors.extend(result.metadata.errors)

        merged = self._merge_deals(all_deals)

        threshold_deals = [d for d in merged if d.discount_percent >= self._discount_threshold]

        threshold_deals.sort(
            key=lambda d: (d.original_price or 0) - d.current_price,
            reverse=True,
        )

        return DiscountResult(
            deals=threshold_deals[:limit],
            total=len(threshold_deals),
            threshold=self._discount_threshold,
            errors=errors,
        )

    async def get_genre_deals(self, *, limit: int = 20) -> DiscountResult:
        """Return deals that match at least one favorite genre keyword.

        Args:
            limit: Maximum number of deals to return.

        Returns:
            A ``DiscountResult`` with genre-filtered deals, or empty when
            ``favorite_genres`` is not configured.
        """
        if not self._favorite_genres:
            return DiscountResult(deals=[], total=0, threshold=self._discount_threshold, errors=[])

        all_result = await self.get_crazy_discounts(limit=limit * 3)
        genre_deals = [d for d in all_result.deals if self._matches_favorite_genres(d)]
        return DiscountResult(
            deals=genre_deals[:limit],
            total=len(genre_deals),
            threshold=self._discount_threshold,
            errors=all_result.errors,
        )

    async def enrich_with_historical_low(self, deal: Deal) -> Deal:
        """Check ITAD for historical low price and attach it to the deal.

        Args:
            deal: A ``Deal`` instance to enrich.

        Returns:
            The same ``Deal`` with ``raw_metadata`` updated if ITAD data
            was available.
        """
        if not self._itad_provider:
            return deal

        plain_id = (deal.raw_metadata or {}).get("itad_plain_id")
        steam_app_id = getattr(deal, "steam_app_id", None)
        target_id = plain_id or steam_app_id
        if not target_id:
            return deal

        try:
            itad = cast("Any", self._itad_provider)
            lowest = await itad.get_lowest_price(
                plain_id if plain_id else str(steam_app_id),
            )
            if lowest and lowest.get("lowest_price") is not None:
                deal.raw_metadata = {
                    **(deal.raw_metadata or {}),
                    "historical_low": lowest["lowest_price"],
                    "historical_low_date": lowest.get("lowest_recorded_date"),
                    "is_historical_low": deal.current_price <= lowest["lowest_price"],
                }
        except Exception:
            logger.debug("Failed to fetch historical low for %s", deal.title)
        return deal

    @staticmethod
    async def _safe_get_deals(
        provider: Any,
        *,
        limit: int,
    ) -> ProviderResult:
        """Call provider.get_deals() and return a result on any error.

        Args:
            provider: A ``DataProvider`` (or decorated proxy).
            limit: Maximum number of deals to request.

        Returns:
            A ``ProviderResult`` — either the real result or an error result.
        """
        try:
            if not hasattr(provider, "get_deals"):
                return ProviderResult(
                    metadata=ProviderMetadata(provider=provider.name),
                )
            return await provider.get_deals(limit=limit)  # type: ignore[no-any-return]
        except Exception as e:
            logger.exception("Deals error from %s", provider.name)
            return ProviderResult(
                metadata=ProviderMetadata(
                    provider=provider.name,
                    errors=[
                        {
                            "type": "deals_error",
                            "provider": provider.name,
                            "detail": str(e),
                        }
                    ],
                ),
            )

    @staticmethod
    def _merge_deals(deals: list[Deal]) -> list[Deal]:
        """Deduplicate deals by ``store_url`` then fallback key.

        When the same deal appears from multiple providers, keep the record
        with the better discount and combine ``provider_names``.

        Args:
            deals: Raw list of ``Deal`` objects from all providers.

        Returns:
            Deduplicated deal list with merged provider_names.
        """
        seen: dict[str, Deal] = {}

        for deal in deals:
            key = (
                str(deal.store_url)
                if deal.store_url
                else f"{deal.title.lower()}-{deal.store.value}"
            )
            if key in seen:
                existing = seen[key]
                if deal.discount_percent > existing.discount_percent:
                    existing.discount_percent = deal.discount_percent
                    existing.current_price = min(existing.current_price, deal.current_price)
                existing.provider_names = list(
                    set(existing.provider_names + deal.provider_names),
                )
            else:
                seen[key] = deal

        return list(seen.values())

    def _matches_favorite_genres(self, deal: Deal) -> bool:
        """Check if a deal's genres or title match any favorite genre.

        Args:
            deal: A ``Deal`` instance.

        Returns:
            True if the deal matches at least one favorite genre.
        """
        if not self._favorite_genres:
            return True
        deal_genres = [g.lower() for g in (deal.raw_metadata or {}).get("genres", [])]
        title_lower = deal.title.lower()
        for genre in self._favorite_genres:
            genre_lower = genre.lower()
            if genre_lower in deal_genres:
                return True
            if genre_lower in title_lower:
                return True
        return False
