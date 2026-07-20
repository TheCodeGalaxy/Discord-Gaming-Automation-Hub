"""Search service — fan-out, merge, rank, and autocomplete.

Orchestrates parallel searches across all providers, deduplicates results,
ranks by relevance, and returns a unified ``SearchResult``.
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, cast

from gaming_hub.core.exceptions import ProviderError, ProviderRateLimitError
from gaming_hub.data.cache.decorator import CachedProviderDecorator
from gaming_hub.models.dto.provider import ProviderMetadata, ProviderResult
from gaming_hub.models.dto.request import SearchRequest

if TYPE_CHECKING:
    from gaming_hub.core.interfaces import CacheBackend, DataProvider
    from gaming_hub.models.domain.deal import Deal
    from gaming_hub.models.domain.game import Game

logger = logging.getLogger(__name__)


@dataclass
class AutocompleteItem:
    """A single autocomplete suggestion for Discord slash commands."""

    label: str
    value: str
    provider: str


@dataclass
class SearchResult:
    """Unified search result aggregated from all providers."""

    games: list[Game] = field(default_factory=list)
    deals: list[Deal] = field(default_factory=list)
    total_games: int = 0
    total_deals: int = 0
    errors: list[dict[str, Any]] = field(default_factory=list)
    took_ms: float = 0.0


class SearchService:
    """Orchestrate parallel search across all registered providers."""

    def __init__(self, providers: list[DataProvider], cache: CacheBackend) -> None:
        """Wrap each provider with caching and store internally.

        Args:
            providers: List of ``DataProvider`` instances (raw, not wrapped).
            cache: ``CacheBackend`` instance shared across all providers.
        """
        self._providers = [
            CachedProviderDecorator(p, cache) for p in providers
        ]

    async def search(self, request: SearchRequest) -> SearchResult:
        """Fan-out search to all providers, merge, deduplicate, and rank.

        Args:
            request: The search parameters (query, limit, exact, etc.).

        Returns:
            A ``SearchResult`` with merged games and deals sorted by relevance.
        """
        start = time.monotonic()

        tasks = [
            self._safe_search(provider, request)
            for provider in self._providers
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        all_games: list[Game] = []
        all_deals: list[Deal] = []
        provider_errors: list[dict[str, Any]] = []

        for provider, result in zip(self._providers, results, strict=False):
            if isinstance(result, Exception):
                provider_errors.append({
                    "provider": provider.name,
                    "error": str(result),
                })
                continue
            assert isinstance(result, ProviderResult)
            all_games.extend(result.games or [])
            all_deals.extend(result.deals or [])
            if result.metadata.errors:
                provider_errors.extend(result.metadata.errors)

        merged_games = self._merge_games(all_games)
        merged_deals = self._merge_deals(all_deals)

        sorted_games = self._rank_results(merged_games, request)
        sorted_deals = self._rank_deals(merged_deals)

        elapsed = time.monotonic() - start

        return SearchResult(
            games=sorted_games[:request.limit],
            deals=sorted_deals[:request.limit],
            total_games=len(sorted_games),
            total_deals=len(sorted_deals),
            errors=provider_errors,
            took_ms=round(elapsed * 1000, 2),
        )

    async def autocomplete(self, query: str, limit: int = 10) -> list[AutocompleteItem]:
        """Return lightweight autocomplete suggestions.

        Args:
            query: The partial user input.
            limit: Maximum number of suggestions to return.

        Returns:
            A list of ``AutocompleteItem`` instances.
        """
        request = SearchRequest(query=query, limit=limit)
        result = await self.search(request)
        return [
            AutocompleteItem(
                label=game.title,
                value=str(game.steam_app_id or game.id),
                provider=game.provider_name,
            )
            for game in result.games[:limit]
        ]

    async def _safe_search(
        self,
        provider: Any,
        request: SearchRequest,
    ) -> ProviderResult:
        """Call provider.search() and return a ``ProviderResult`` on any error.

        Args:
            provider: A ``DataProvider`` (or decorated proxy).
            request: The search request to forward.

        Returns:
            A ``ProviderResult`` — either the real result from the provider or
            an error result with failure metadata.
        """
        try:
            result = cast("ProviderResult", await provider.search(request))
            return result
        except ProviderRateLimitError:
            logger.warning("Rate limited by %s", provider.name)
            return ProviderResult(
                metadata=ProviderMetadata(
                    provider=provider.name,
                    errors=[{"type": "rate_limit", "provider": provider.name}],
                ),
            )
        except ProviderError as e:
            logger.error("Provider error from %s: %s", provider.name, e)
            return ProviderResult(
                metadata=ProviderMetadata(
                    provider=provider.name,
                    errors=[{
                        "type": "provider_error",
                        "provider": provider.name,
                        "detail": str(e),
                    }],
                ),
            )
        except Exception as e:
            logger.exception("Unexpected error from %s", provider.name)
            return ProviderResult(
                metadata=ProviderMetadata(
                    provider=provider.name,
                    errors=[{
                        "type": "unexpected",
                        "provider": provider.name,
                        "detail": str(e),
                    }],
                ),
            )

    @staticmethod
    def _merge_games(games: list[Game]) -> list[Game]:
        """Deduplicate games by ``steam_app_id`` then normalized title.

        Args:
            games: Raw list from all providers.

        Returns:
            Deduplicated game list preserving insertion order.
        """
        seen_ids: set[int | str] = set()
        seen_titles: set[str] = set()
        merged: list[Game] = []

        for game in games:
            dedup_key = game.steam_app_id or game.id
            title_key = SearchService._normalize_title(game.title)

            if dedup_key and dedup_key in seen_ids:
                continue
            if title_key in seen_titles:
                continue

            if dedup_key:
                seen_ids.add(dedup_key)
            seen_titles.add(title_key)
            merged.append(game)

        return merged

    @staticmethod
    def _merge_deals(deals: list[Deal]) -> list[Deal]:
        """Deduplicate deals by deal ID.

        Args:
            deals: Raw list from all providers.

        Returns:
            Deduplicated deal list preserving insertion order.
        """
        seen: set[str] = set()
        merged: list[Deal] = []
        for deal in deals:
            if deal.id and deal.id in seen:
                continue
            if deal.id:
                seen.add(deal.id)
            merged.append(deal)
        return merged

    @staticmethod
    def _normalize_title(title: str) -> str:
        """Normalize a game title for deduplication comparison.

        Strips punctuation, lowercases, removes whitespace.

        Args:
            title: Raw game title.

        Returns:
            Normalized string suitable for comparison.
        """
        return re.sub(r"[^a-z0-9]", "", title.lower().strip())

    @staticmethod
    def _rank_results(games: list[Game], request: SearchRequest) -> list[Game]:
        """Rank games by relevance to the search query.

        Args:
            games: Deduplicated game list.
            request: The original search request (for query terms).

        Returns:
            Games sorted by relevance score descending.
        """
        query_lower = request.query.lower()
        query_terms = set(query_lower.split())

        def score(game: Game) -> float:
            s = 0.0
            title_lower = game.title.lower()
            if title_lower == query_lower:
                s += 100.0
            elif title_lower.startswith(query_lower):
                s += 50.0
            title_terms = set(title_lower.split())
            matching_terms = query_terms & title_terms
            s += len(matching_terms) * 10.0
            if game.steam_app_id:
                s += 5.0
            if game.cover_url:
                s += 2.0
            return s

        return sorted(games, key=score, reverse=True)

    @staticmethod
    def _rank_deals(deals: list[Deal]) -> list[Deal]:
        """Rank deals by discount percentage descending.

        Args:
            deals: Deduplicated deal list.

        Returns:
            Deals sorted by discount percent descending.
        """
        return sorted(deals, key=lambda d: d.discount_percent, reverse=True)
