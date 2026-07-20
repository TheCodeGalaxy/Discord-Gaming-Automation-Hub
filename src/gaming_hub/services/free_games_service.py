"""Free games service — aggregate, deduplicate, and track expiry.

Aggregates currently-free and upcoming-free games across all providers,
deduplicates by ``steam_app_id`` and normalized title, tracks expiry dates,
and flags games expiring within a configurable window.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from typing import TYPE_CHECKING, Any

from gaming_hub.data.cache.decorator import CachedProviderDecorator
from gaming_hub.models.dto.provider import ProviderMetadata, ProviderResult

if TYPE_CHECKING:
    from gaming_hub.core.interfaces import CacheBackend, DataProvider

logger = logging.getLogger(__name__)


@dataclass
class FreeGamesResult:
    """Aggregated free games result from all providers."""

    current: list[Any] = field(default_factory=list)
    total: int = 0
    expiring_soon: list[Any] = field(default_factory=list)
    errors: list[dict[str, Any]] = field(default_factory=list)
    fetched_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class FreeGamesService:
    """Orchestrate free game aggregation across all registered providers."""

    def __init__(
        self,
        providers: list[DataProvider],
        cache: CacheBackend,
        expiry_hours: int = 48,
    ) -> None:
        """Wrap each provider with caching and store internally.

        Args:
            providers: List of ``DataProvider`` instances (raw, not wrapped).
            cache: ``CacheBackend`` instance shared across all providers.
            expiry_hours: Hours before ``free_until`` to flag as "expiring soon".
        """
        self._providers = [
            CachedProviderDecorator(p, cache) for p in providers
        ]
        self._expiry_hours = expiry_hours

    async def get_current(self) -> FreeGamesResult:
        """Aggregate currently-free games from all providers.

        Returns:
            A ``FreeGamesResult`` with merged, sorted games and expiring-soon subset.
        """
        tasks = [
            self._safe_free_games(provider, upcoming=False)
            for provider in self._providers
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        all_games: list[Any] = []
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
            if result.metadata.errors:
                provider_errors.extend(result.metadata.errors)

        merged = self._merge_free_games(all_games)
        sorted_games = sorted(merged, key=lambda g: g.free_until or date.max)

        return FreeGamesResult(
            current=sorted_games,
            total=len(sorted_games),
            expiring_soon=self._filter_expiring_soon(sorted_games),
            errors=provider_errors,
        )

    async def get_upcoming(self) -> FreeGamesResult:
        """Aggregate upcoming-free games (Epic only).

        Returns:
            A ``FreeGamesResult`` with upcoming free games.
        """
        tasks = [
            self._safe_free_games(provider, upcoming=True)
            for provider in self._providers
            if provider.name == "epic"
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        provider_errors: list[dict[str, Any]] = []

        for provider, result in zip(
            [p for p in self._providers if p.name == "epic"],
            results,
            strict=False,
        ):
            if isinstance(result, Exception):
                provider_errors.append({
                    "provider": provider.name,
                    "error": str(result),
                })
                continue
            assert isinstance(result, ProviderResult)
            provider_errors.extend(result.metadata.errors)

        # Collect upcoming games from all results
        all_upcoming: list[Any] = []
        for r in results:
            if isinstance(r, ProviderResult):
                all_upcoming.extend(r.games or [])

        merged = self._merge_free_games(all_upcoming)
        sorted_games = sorted(merged, key=lambda g: g.coming_soon_date or date.max)

        return FreeGamesResult(
            current=sorted_games,
            total=len(sorted_games),
            errors=provider_errors,
        )

    async def get_expiring_soon(self) -> list[Any]:
        """Return games expiring within the configured expiry window.

        Returns:
            List of games whose ``free_until`` is within ``expiry_hours``.
        """
        result = await self.get_current()
        return result.expiring_soon

    @staticmethod
    async def _safe_free_games(
        provider: Any,
        *,
        upcoming: bool,
    ) -> ProviderResult:
        """Call provider.get_free_games() and return a result on any error.

        Args:
            provider: A ``DataProvider`` (or decorated proxy).
            upcoming: Whether to fetch upcoming (True) or current (False) free games.

        Returns:
            A ``ProviderResult`` — either the real result or an error result.
        """
        try:
            if not hasattr(provider, "get_free_games"):
                return ProviderResult(
                    metadata=ProviderMetadata(provider=provider.name),
                )
            return await provider.get_free_games(upcoming=upcoming)  # type: ignore[no-any-return]
        except Exception as e:
            logger.exception("Free games error from %s", provider.name)
            return ProviderResult(
                metadata=ProviderMetadata(
                    provider=provider.name,
                    errors=[{
                        "type": "free_games_error",
                        "provider": provider.name,
                        "detail": str(e),
                    }],
                ),
            )

    @staticmethod
    def _merge_free_games(games: list[Any]) -> list[Any]:
        """Deduplicate free games by ``steam_app_id`` then normalized title.

        When the same game appears from multiple providers, keep the record
        with the richer metadata and combine ``provider_names``.

        Args:
            games: Raw list of ``Game`` objects from all providers.

        Returns:
            Deduplicated game list with merged provider_names.
        """
        seen: dict[str, Any] = {}

        for game in games:
            # Ensure provider_names is populated
            if not game.provider_names:
                game.provider_names = [game.provider_name]

            key = str(game.steam_app_id or game.title.lower().strip())
            if key in seen:
                existing = seen[key]
                existing_score = FreeGamesService._completeness_score(existing)
                new_score = FreeGamesService._completeness_score(game)
                if new_score > existing_score:
                    game.provider_names = list(
                        set(existing.provider_names + game.provider_names),
                    )
                    if existing.free_until and game.free_until:
                        game.free_until = min(existing.free_until, game.free_until)
                    elif existing.free_until:
                        game.free_until = existing.free_until
                    seen[key] = game
                else:
                    existing.provider_names = list(
                        set(existing.provider_names + game.provider_names),
                    )
                    if game.free_until and existing.free_until:
                        existing.free_until = min(existing.free_until, game.free_until)
                    elif game.free_until and not existing.free_until:
                        existing.free_until = game.free_until
            else:
                seen[key] = game

        return list(seen.values())

    @staticmethod
    def _completeness_score(game: Any) -> int:
        """Score a game record by data completeness.

        Higher score means richer metadata (more fields populated).

        Args:
            game: A ``Game`` instance.

        Returns:
            An integer score (0-5).
        """
        score = 0
        min_desc_length = 50
        if game.cover_url:
            score += 1
        if game.genres:
            score += 1
        if game.description and len(game.description) > min_desc_length:
            score += 1
        if game.developers:
            score += 1
        if game.raw_metadata:
            score += 1
        return score

    def _filter_expiring_soon(
        self,
        games: list[Any],
    ) -> list[Any]:
        """Filter games expiring within the configured window.

        Args:
            games: List of ``Game`` objects (should be sorted by ``free_until``).

        Returns:
            Games whose ``free_until`` is within ``expiry_hours`` from now.
        """
        now = datetime.now(UTC).date()
        deadline = now + timedelta(hours=self._expiry_hours)
        return [g for g in games if g.free_until and g.free_until <= deadline]
