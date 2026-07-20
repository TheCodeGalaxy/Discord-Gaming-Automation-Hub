"""Top games service — compute weekly trending game rankings.

Combines deal discounts, review scores and player counts into a composite
score, then ranks games into shuffled tiers for the ``#top-this-week``
Discord channel.
"""
# ruff: noqa: PLR2004 — tier thresholds 0.7 / 0.4 are documented magic values

from __future__ import annotations

import asyncio
import logging
import random
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from typing import TYPE_CHECKING, Any

from gaming_hub.data.cache.decorator import CachedProviderDecorator
from gaming_hub.models.dto.provider import ProviderMetadata, ProviderResult
from gaming_hub.models.dto.request import SearchRequest

if TYPE_CHECKING:
    from gaming_hub.core.interfaces import CacheBackend, DataProvider
    from gaming_hub.models.domain.deal import Deal

logger = logging.getLogger(__name__)


@dataclass
class ScoringWeights:
    """Configurable weights for composite score computation."""

    discount_depth: float = 0.30
    review_score: float = 0.25
    popularity: float = 0.20
    freshness: float = 0.15
    completeness: float = 0.10


@dataclass
class GameSignal:
    """Raw signals collected for one game before scoring."""

    game_id: str
    title: str | None = None
    discount_percent: float = 0.0
    savings_amount: float = 0.0
    review_score: float | None = None
    review_count: int = 0
    current_players: int | None = None
    is_trending: bool = False
    providers: set[str] = field(default_factory=set)


@dataclass
class ScoredGame:
    """A game with its computed composite score and underlying signals."""

    game_id: str
    title: str
    score: float
    signals: GameSignal


@dataclass
class TopGamesResult:
    """Weekly top games ranking result."""

    games: list[ScoredGame]
    total: int
    week_ending: date
    computed_at: datetime


class TopGamesService:
    """Compute weekly trending game rankings from all data sources.

    Collects deal discounts, popularity signals (player counts / trending),
    and review scores, then produces a ranked list with tiered shuffling
    for presentation variety.
    """

    def __init__(
        self,
        providers: list[DataProvider],
        cache: CacheBackend,
        weights: ScoringWeights | None = None,
    ) -> None:
        """Wrap providers and store references.

        Args:
            providers: List of ``DataProvider`` instances (raw, not wrapped).
            cache: ``CacheBackend`` instance shared across all providers.
            weights: Optional ``ScoringWeights``; defaults are used when None.
        """
        self._providers = [CachedProviderDecorator(p, cache) for p in providers]
        self._raw_providers: dict[str, DataProvider] = {p.name: p for p in providers}
        self._cache = cache
        self._weights = weights or ScoringWeights()

    async def get_weekly_top(self, *, limit: int = 20) -> TopGamesResult:
        """Return cached weekly ranking or compute a fresh one.

        The result is cached for 6 hours (21 600 seconds). The cache key
        includes a version (``v1``) to allow cache busting when the scoring
        algorithm changes.

        Args:
            limit: Maximum number of games to return.

        Returns:
            A ``TopGamesResult`` with ``games`` sorted by descending score.
        """
        cache_key = "top_games:weekly:v1"
        cached: TopGamesResult | None = await self._cache.get(cache_key)
        if cached is not None:
            return cached

        signals = await self._collect_signals()
        scored = self._compute_scores(signals)
        ranked = self._apply_shuffled_ranking(scored, limit)

        result = TopGamesResult(
            games=ranked,
            total=len(ranked),
            week_ending=self._week_ending(),
            computed_at=datetime.now(UTC),
        )

        await self._cache.set(cache_key, result, ttl=21600)
        return result

    async def _collect_signals(self) -> list[GameSignal]:
        """Collect deal, trending, and review signals from all providers.

        Returns:
            A list of ``GameSignal`` objects keyed by game ID.
        """
        signals: dict[str, GameSignal] = {}

        # 1. Deals from CheapShark and ITAD (discount depth signal)
        deal_results = await asyncio.gather(
            self._safe_get_deals(limit=100),
            return_exceptions=True,
        )
        for result in deal_results:
            if isinstance(result, ProviderResult):
                for deal in result.deals or []:
                    game_id = self._resolve_game_id(deal)
                    if not game_id:
                        continue
                    signal = signals.setdefault(
                        game_id,
                        GameSignal(game_id=game_id),
                    )
                    signal.discount_percent = max(
                        signal.discount_percent,
                        deal.discount_percent,
                    )
                    signal.savings_amount = max(
                        signal.savings_amount,
                        (deal.original_price or deal.current_price) - deal.current_price,
                    )
                    signal.providers.add(deal.store.value)
                    signal.title = signal.title or deal.title

        # 2. Trending from Steam (popularity signal)
        steam = self._get_provider("steam_community")
        if steam:
            try:
                trending_result = await self._safe_get_trending(steam, limit=50)
                for game in trending_result.games or []:
                    game_id = str(game.steam_app_id) if game.steam_app_id else game.id
                    signal = signals.setdefault(
                        game_id,
                        GameSignal(game_id=game_id),
                    )
                    if game.raw_metadata:
                        signal.current_players = game.raw_metadata.get(
                            "current_players",
                        )
                    signal.is_trending = True
                    signal.title = signal.title or game.title
            except Exception:
                logger.exception("Failed to fetch trending from Steam")

        # 2b. RAWG popular games (review-score & freshness signal)
        rawg = self._get_provider("rawg")
        if rawg:
            try:
                rawg_result = await self._safe_get_trending(rawg, limit=40)
                for game in rawg_result.games or []:
                    game_id = game.id
                    signal = signals.setdefault(
                        game_id,
                        GameSignal(game_id=game_id),
                    )
                    if game.metacritic_score is not None:
                        signal.review_score = max(
                            signal.review_score or 0,
                            float(game.metacritic_score),
                        )
                    if game.steam_review_score is not None and signal.review_score is None:
                        signal.review_score = game.steam_review_score
                    signal.is_trending = signal.is_trending or True
                    signal.title = signal.title or game.title
                    signal.providers.add("rawg")
            except Exception:
                logger.exception("Failed to fetch trending from RAWG")

        # 3. Review scores from Steam appdetails (quality signal)
        for game_id in list(signals.keys()):
            if signals[game_id].review_score is not None:
                continue
            try:
                review_data = await self._lookup_steam_reviews(game_id)
                if review_data:
                    signals[game_id].review_score = review_data.get("review_score")
                    signals[game_id].review_count = review_data.get("review_count", 0)
            except Exception:
                continue

        return list(signals.values())

    def _compute_scores(self, signals: list[GameSignal]) -> list[ScoredGame]:
        """Normalize signals to 0-1 range and compute weighted composite score.

        Args:
            signals: Raw ``GameSignal`` list.

        Returns:
            A list of ``ScoredGame`` sorted by descending ``score``.
        """
        now = datetime.now(UTC)

        max_discount = max((s.discount_percent for s in signals), default=0)
        max_savings = max((s.savings_amount for s in signals), default=0)
        max_review = 100.0
        max_players = max((s.current_players or 0 for s in signals), default=0)

        scored: list[ScoredGame] = []
        for signal in signals:
            discount_norm = (signal.discount_percent / max_discount) if max_discount > 0 else 0
            savings_norm = (signal.savings_amount / max_savings) if max_savings > 0 else 0
            review_norm = (signal.review_score or 0) / max_review
            players_norm = ((signal.current_players or 0) / max_players) if max_players > 0 else 0
            freshness_norm = self._freshness_score(signal, now)

            total_score = (
                self._weights.discount_depth * max(discount_norm, savings_norm * 0.5)
                + self._weights.review_score * review_norm
                + self._weights.popularity * players_norm
                + self._weights.freshness * freshness_norm
                + self._weights.completeness * (1.0 if signal.title and signal.providers else 0.5)
            )

            scored.append(
                ScoredGame(
                    game_id=signal.game_id,
                    title=signal.title or "Unknown",
                    score=total_score,
                    signals=signal,
                )
            )

        return sorted(scored, key=lambda x: x.score, reverse=True)

    @staticmethod
    def _apply_shuffled_ranking(
        scored: list[ScoredGame],
        limit: int,
    ) -> list[ScoredGame]:
        """Shuffle games within score tiers for presentation variety.

        Top tier (score ≥ 0.7), middle (0.4-0.7), bottom (< 0.4). Games
        at the top always stay in the first block, but their internal
        order varies between refreshes.

        Args:
            scored: Pre-sorted scored games.
            limit: Maximum games to return.

        Returns:
            Up to ``limit`` games with tiered shuffle applied.
        """
        if not scored:
            return []

        tiers: dict[str, list[ScoredGame]] = {"top": [], "mid": [], "low": []}

        for game in scored:
            if game.score >= 0.7:
                tiers["top"].append(game)
            elif game.score >= 0.4:
                tiers["mid"].append(game)
            else:
                tiers["low"].append(game)

        for tier_list in tiers.values():
            random.shuffle(tier_list)

        ordered = tiers["top"] + tiers["mid"] + tiers["low"]
        return ordered[:limit]

    @staticmethod
    def _week_ending() -> date:
        """Return the upcoming Saturday date.

        If today is Saturday, returns *next* Saturday (7 days away), not
        today. This ensures the weekly period always ends on a future date.

        Returns:
            A ``date`` representing the upcoming Saturday.
        """
        today = date.today()
        days_until_saturday = (5 - today.weekday()) % 7
        if days_until_saturday == 0:
            days_until_saturday = 7
        return today + timedelta(days=days_until_saturday)

    @staticmethod
    def _resolve_game_id(deal: Deal) -> str | None:
        """Resolve a stable game identifier from a deal object.

        Preference order: Steam App ID (from raw_metadata) → ITAD plain ID
        → CheapShark deal ID. Each ID is prefixed with the provider name to
        guarantee uniqueness across providers.

        Args:
            deal: A ``Deal`` instance.

        Returns:
            A provider-prefixed game ID string, or ``None`` if no ID found.
        """
        raw = deal.raw_metadata or {}
        steam_id = raw.get("steam_app_id")
        if steam_id:
            return f"steam:{steam_id}"
        itad_id = raw.get("itad_plain_id")
        if itad_id:
            return f"itad:{itad_id}"
        cs_id = raw.get("cheapshark_deal_id")
        if cs_id:
            return f"cheapshark:{cs_id}"
        return None

    def _get_provider(self, name: str) -> DataProvider | None:
        """Look up a raw provider by name.

        Args:
            name: Provider name to find.

        Returns:
            The ``DataProvider`` instance, or ``None`` if not registered.
        """
        return self._raw_providers.get(name)

    @staticmethod
    def _freshness_score(signal: GameSignal, now: datetime) -> float:
        """Compute a freshness score for a game signal.

        Trending games receive full freshness; non-trending games get a
        neutral baseline.

        Args:
            signal: The ``GameSignal`` to evaluate.
            now: Current UTC datetime.

        Returns:
            A float in the 0-1 range.
        """
        if signal.is_trending:
            return 1.0
        return 0.3

    @staticmethod
    async def _safe_get_trending(
        provider: DataProvider,
        limit: int,
    ) -> ProviderResult:
        """Safely call ``get_trending`` on a provider.

        Args:
            provider: A ``DataProvider`` with ``get_trending``.
            limit: Number of trending games to fetch.

        Returns:
            A ``ProviderResult`` or an error-wrapped result.
        """
        try:
            return await provider.get_trending(limit=limit)  # type: ignore[no-any-return, attr-defined]
        except Exception as e:
            logger.exception("Trending error from %s", provider.name)
            return ProviderResult(
                metadata=ProviderMetadata(
                    provider=provider.name,
                    errors=[
                        {
                            "type": "trending",
                            "provider": provider.name,
                            "detail": str(e),
                        }
                    ],
                ),
            )

    async def _safe_get_deals(self, limit: int = 100) -> ProviderResult:
        """Safely gather deals from all cached providers.

        Args:
            limit: Max deals per provider.

        Returns:
            A combined ``ProviderResult`` with deals from all providers.
        """
        tasks = [p.get_deals(limit=limit) for p in self._providers]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        combined = ProviderResult(
            metadata=ProviderMetadata(provider="top_games"),
        )
        for r in results:
            if isinstance(r, ProviderResult):
                combined.deals.extend(r.deals or [])
                if r.metadata.errors:
                    combined.metadata.errors.extend(r.metadata.errors)
            elif isinstance(r, Exception):
                combined.metadata.errors.append(
                    {
                        "type": "deals",
                        "detail": str(r),
                    }
                )
        return combined

    async def _lookup_steam_reviews(
        self,
        game_id: str,
    ) -> dict[str, Any] | None:
        """Look up Steam review data for a game ID.

        If the ``game_id`` begins with a known provider prefix, it is
        stripped before lookup. Only ``steam:*`` IDs are resolved;
        others return ``None``.

        Args:
            game_id: Provider-prefixed game ID.

        Returns:
            A dict with ``review_score`` and ``review_count``, or ``None``.
        """
        if game_id.startswith("steam:"):
            raw_id = game_id.replace("steam:", "")
        else:
            return None

        try:
            app_id = int(raw_id)
        except (ValueError, TypeError):
            return None

        steam = self._get_provider("steam_community")
        if steam is None:
            return None

        try:
            search_result = await steam.search(
                SearchRequest(steam_app_id=app_id, limit=1),
            )
        except Exception:
            return None

        if search_result.games:
            game = search_result.games[0]
            return {
                "review_score": game.steam_review_score,
                "review_count": game.steam_review_count,
            }
        return None
