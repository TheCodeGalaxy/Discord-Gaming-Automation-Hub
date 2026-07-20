"""Surprise service — random game discovery for the /surprise slash command.

Selects a random high-rated game from a curated pool, filters by genre,
and tracks session history to avoid repeats.
"""

from __future__ import annotations

import asyncio
import logging
import random
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from gaming_hub.data.cache.decorator import CachedProviderDecorator
from gaming_hub.models.dto.request import SearchRequest

if TYPE_CHECKING:
    from gaming_hub.core.interfaces import CacheBackend, DataProvider
    from gaming_hub.models.domain.game import Game

logger = logging.getLogger(__name__)


@dataclass
class SurpriseResult:
    """Result of a surprise game selection."""

    game: Game | None = None
    session_id: str = ""
    remaining_in_pool: int = 0


class SurpriseService:
    """Select random high-rated games with session-based history tracking.

    The game pool is built from all configured providers by querying each
    one concurrently, merging and de-duplicating their catalogs, and filtering
    by rating before selection.
    """

    def __init__(
        self,
        providers: list[DataProvider],
        cache: CacheBackend,
        favorite_genres: list[str] | None = None,
        min_rating: int = 70,
    ) -> None:
        """Wrap each provider with caching and store internally.

        Args:
            providers: List of ``DataProvider`` instances.
            cache: ``CacheBackend`` instance shared across all providers.
            favorite_genres: Genre keywords for genre-biased selection.
            min_rating: Minimum Steam review score (0-100) for pool inclusion.
        """
        self._providers = [CachedProviderDecorator(p, cache) for p in providers]
        self._favorite_genres = favorite_genres or []
        self._min_rating = min_rating
        self._seen_history: dict[str, list[str]] = {}

    async def get_random(
        self,
        session_id: str = "default",
        *,
        genre: str | None = None,
    ) -> Game | None:
        """Select a random game from the pool, filtered by genre and history.

        Args:
            session_id: Opaque session identifier for history tracking.
            genre: Optional genre filter (overrides ``favorite_genres``).

        Returns:
            A ``Game`` instance or ``None`` if the pool is empty.
        """
        pool = await self._build_pool()

        if genre:
            pool = [
                g
                for g in pool
                if genre.lower() in [x.lower() for x in (g.genres or [])]
                or genre.lower() in [x.lower() for x in (g.tags or [])]
            ]

        seen_ids = self._seen_history.get(session_id, [])
        available = [g for g in pool if g.id not in seen_ids]

        if not available:
            self._seen_history[session_id] = []
            available = pool

        if not available:
            return None

        chosen = random.choice(available)
        self._seen_history.setdefault(session_id, []).append(chosen.id)
        return chosen

    def _matches_genre(self, game: Game) -> bool:
        """Check if a game's genres match any favorite genre.

        Args:
            game: A ``Game`` instance.

        Returns:
            True if at least one favorite genre matches.
        """
        if not self._favorite_genres:
            return True
        game_genres = [g.lower() for g in (game.genres or [])]
        return any(g.lower() in game_genres for g in self._favorite_genres)

    async def _build_pool(self) -> list[Game]:
        """Build the game pool from provider data.

        Returns:
            A list of ``Game`` objects for random selection.
        """
        pool = await self._fetch_highly_rated_games()
        return pool

    async def _fetch_highly_rated_games(self) -> list[Game]:
        """Fetch high-rated games from every configured provider.

        Queries each provider concurrently, tolerates individual provider
        failures, merges the results into a single de-duplicated pool, drops
        games below ``_min_rating`` (when a rating is present), and returns a
        shuffled list. The warning "Surprise pool is empty" is only emitted
        when every provider returned zero games.
        """
        results = await asyncio.gather(
            *[self._safe_fetch(p) for p in self._providers],
            return_exceptions=True,
        )

        merged: dict[str, Game] = {}
        any_games = False
        for result in results:
            if not isinstance(result, list):
                continue
            games: list[Game] = result
            if not games:
                continue
            any_games = True
            for game in games:
                if game.id not in merged:
                    merged[game.id] = game

        pool = list(merged.values())

        pool = [
            g
            for g in pool
            if not self._has_rating(g) or self._rating(g) >= self._min_rating
        ]

        random.shuffle(pool)

        if not any_games:
            logger.warning("Surprise pool is empty — every provider returned zero games")

        return pool

    @staticmethod
    async def _safe_fetch(provider: Any) -> list[Game]:
        """Fetch games from a single provider, returning [] on any failure."""
        try:
            result = await provider.search(SearchRequest(limit=50))
            if result.games:
                return list(result.games)
        except Exception:
            logger.exception("Surprise provider %s failed", getattr(provider, "name", "?"))
        try:
            if hasattr(provider, "get_deals"):
                deal_result = await provider.get_deals(limit=50)
                if deal_result.deals:
                    from gaming_hub.models.domain.game import Game
                    games: list[Game] = []
                    for deal in deal_result.deals:
                        games.append(
                            Game(
                                id=deal.id,
                                title=deal.title,
                                provider_name=provider.name,
                                provider_url=deal.store_url,
                                raw_metadata=deal.raw_metadata,
                            ),
                        )
                    return games
        except Exception:
            logger.exception("Surprise deals fallback failed for %s", getattr(provider, "name", "?"))
        return []

    @staticmethod
    def _has_rating(game: Game) -> bool:
        """Return True if the game exposes any usable rating signal."""
        return game.steam_review_score is not None or game.metacritic_score is not None

    @staticmethod
    def _rating(game: Game) -> float:
        """Return the best available rating (0-100) for a game."""
        scores = [s for s in (game.steam_review_score, game.metacritic_score) if s is not None]
        return max(scores) if scores else 0.0
