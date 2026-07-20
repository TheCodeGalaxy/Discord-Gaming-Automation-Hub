"""Unit tests for TopGamesService."""
# ruff: noqa: PLR2004 — test assertions use literal magic values for clarity

from __future__ import annotations

from datetime import date
from unittest.mock import patch

import pytest

from gaming_hub.data.cache.in_memory import InMemoryCache
from gaming_hub.models.domain.deal import Deal
from gaming_hub.services.top_games_service import (
    GameSignal,
    ScoredGame,
    ScoringWeights,
    TopGamesService,
)


def _signal(  # noqa: PLR0913
    game_id: str = "steam:1",
    title: str = "Test Game",
    discount_percent: float = 0.0,
    savings_amount: float = 0.0,
    review_score: float | None = None,
    current_players: int | None = None,
    is_trending: bool = False,
    providers: set[str] | None = None,
) -> GameSignal:
    return GameSignal(
        game_id=game_id,
        title=title,
        discount_percent=discount_percent,
        savings_amount=savings_amount,
        review_score=review_score,
        current_players=current_players,
        is_trending=is_trending,
        providers=providers or set(),
    )


@pytest.fixture()
def cache() -> InMemoryCache:
    """Return a fresh in-memory cache."""
    return InMemoryCache(default_ttl=600)


@pytest.mark.unit
class TestTopGamesServiceScore:
    """Score computation and ranking."""

    @pytest.mark.asyncio
    async def test_higher_discount_scores_higher(
        self,
        cache: InMemoryCache,
    ) -> None:
        """Verify a game with 95% discount scores higher than 50%."""
        service = TopGamesService([], cache)

        signals = [
            _signal(
                game_id="steam:1",
                title="Deep Discount",
                discount_percent=95.0,
                savings_amount=50.0,
            ),
            _signal(
                game_id="steam:2",
                title="Mild Discount",
                discount_percent=50.0,
                savings_amount=10.0,
            ),
        ]
        scored = service._compute_scores(signals)
        assert len(scored) == 2
        assert scored[0].title == "Deep Discount"
        assert scored[0].score > scored[1].score

    @pytest.mark.asyncio
    async def test_higher_review_scores_higher(
        self,
        cache: InMemoryCache,
    ) -> None:
        """Verify games with higher review scores rank above when discounts are equal."""
        service = TopGamesService([], cache)

        signals = [
            _signal(
                game_id="steam:1",
                title="Well Reviewed",
                discount_percent=50.0,
                savings_amount=10.0,
                review_score=95.0,
            ),
            _signal(
                game_id="steam:2",
                title="Poorly Reviewed",
                discount_percent=50.0,
                savings_amount=10.0,
                review_score=30.0,
            ),
        ]
        scored = service._compute_scores(signals)
        assert scored[0].title == "Well Reviewed"
        assert scored[0].score > scored[1].score

    @pytest.mark.asyncio
    async def test_empty_signals_returns_empty(
        self,
        cache: InMemoryCache,
    ) -> None:
        """Verify empty signals produce total=0."""
        service = TopGamesService([], cache)

        signals: list[GameSignal] = []
        scored = service._compute_scores(signals)
        assert len(scored) == 0

    def test_scoring_weights_defaults_sum_to_one(self) -> None:
        """Verify default ScoringWeights sum to 1.0."""
        w = ScoringWeights()
        total = w.discount_depth + w.review_score + w.popularity + w.freshness + w.completeness
        assert abs(total - 1.0) < 0.001

    @pytest.mark.asyncio
    async def test_get_weekly_top_cached(
        self,
        cache: InMemoryCache,
    ) -> None:
        """Verify second call within TTL returns cached result."""
        service = TopGamesService([], cache)

        with (
            patch.object(
                service,
                "_collect_signals",
                return_value=[
                    _signal(
                        game_id="steam:1",
                        title="A",
                        discount_percent=80.0,
                        savings_amount=40.0,
                    ),
                ],
            ),
        ):
            first = await service.get_weekly_top(limit=10)
            second = await service.get_weekly_top(limit=10)

        assert first.total == second.total
        assert second.games[0].title == "A"

    @pytest.mark.asyncio
    async def test_get_weekly_top_limit(
        self,
        cache: InMemoryCache,
    ) -> None:
        """Verify limit restricts returned games."""
        service = TopGamesService([], cache)

        signals = [
            _signal(
                game_id=f"steam:{i}",
                title=f"Game {i}",
                discount_percent=float(100 - i),
                savings_amount=50.0,
            )
            for i in range(20)
        ]

        with patch.object(service, "_collect_signals", return_value=signals):
            result = await service.get_weekly_top(limit=5)
        assert result.total <= 5
        assert len(result.games) <= 5

    def test_week_ending_is_saturday(self) -> None:
        """Verify _week_ending always returns a Saturday (weekday=5)."""
        ending = TopGamesService._week_ending()
        assert ending.weekday() == 5  # Saturday

    def test_week_ending_is_future(self) -> None:
        """Verify _week_ending returns a date in the future."""
        ending = TopGamesService._week_ending()
        assert ending > date.today()

    def test_get_weekly_top_not_async(self) -> None:
        """Marker test for weekend check — saturday is always future."""
        ending = TopGamesService._week_ending()
        assert ending.weekday() == 5

    @pytest.mark.asyncio
    async def test_cache_returns_same_object(
        self,
        cache: InMemoryCache,
    ) -> None:
        """Verify cache actually stores and retrieves."""
        service = TopGamesService([], cache)

        with (
            patch.object(
                service,
                "_collect_signals",
                return_value=[
                    _signal(
                        game_id="steam:1",
                        title="Cached",
                        discount_percent=80.0,
                        savings_amount=40.0,
                    ),
                ],
            ),
        ):
            first = await service.get_weekly_top(limit=10)
            second = await service.get_weekly_top(limit=10)

        assert first is second


@pytest.mark.unit
class TestTopGamesServiceShuffledRanking:
    """_apply_shuffled_ranking behavior."""

    def _make_scored(self, game_id: str, score: float) -> ScoredGame:
        return ScoredGame(
            game_id=game_id,
            title=f"Game {game_id}",
            score=score,
            signals=_signal(game_id=game_id),
        )

    def test_top_tier_always_first(self) -> None:
        """Verify top-tier games (score >= 0.7) always appear before mid/low."""
        scored = [
            self._make_scored("a", 0.3),
            self._make_scored("b", 0.8),
            self._make_scored("c", 0.5),
            self._make_scored("d", 0.9),
        ]

        results = [TopGamesService._apply_shuffled_ranking(scored, limit=10) for _ in range(10)]

        for ranked in results:
            low_titles = {g.game_id for g in ranked if g.score < 0.7}
            if low_titles:
                highest_low_index = max(i for i, g in enumerate(ranked) if g.score < 0.7)
                lowest_top_index = min(i for i, g in enumerate(ranked) if g.score >= 0.7)
                assert lowest_top_index < highest_low_index

    def test_shuffle_variation(self) -> None:
        """Verify that multiple shuffles produce different orderings within tiers."""
        scored = [
            self._make_scored("a", 0.9),
            self._make_scored("b", 0.8),
            self._make_scored("c", 0.3),
            self._make_scored("d", 0.2),
        ]

        orders = set()
        for _ in range(20):
            ranked = TopGamesService._apply_shuffled_ranking(scored, limit=10)
            orders.add(tuple(g.game_id for g in ranked))

        # At least 2 different orderings should occur
        assert len(orders) >= 2

    def test_empty_scored(self) -> None:
        """Verify empty input returns empty list."""
        result = TopGamesService._apply_shuffled_ranking([], limit=10)
        assert result == []

    def test_limit_respected(self) -> None:
        """Verify limit truncates output."""
        scored = [self._make_scored(f"g{i}", 0.5) for i in range(20)]
        result = TopGamesService._apply_shuffled_ranking(scored, limit=5)
        assert len(result) == 5


@pytest.mark.unit
class TestTopGamesServiceResolveGameId:
    """_resolve_game_id behavior."""

    def test_steam_id_preferred(self) -> None:
        """Verify Steam App ID is chosen over ITAD plain ID."""
        deal = Deal(
            id="d1",
            title="Test",
            current_price=10.0,
            raw_metadata={"steam_app_id": 730, "itad_plain_id": "csgo"},
        )
        result = TopGamesService._resolve_game_id(deal)
        assert result == "steam:730"

    def test_itad_fallback(self) -> None:
        """Verify ITAD plain ID is used when no Steam ID exists."""
        deal = Deal(
            id="d2",
            title="Test",
            current_price=10.0,
            raw_metadata={"itad_plain_id": "witcher3"},
        )
        result = TopGamesService._resolve_game_id(deal)
        assert result == "itad:witcher3"

    def test_cheapshark_fallback(self) -> None:
        """Verify CheapShark ID is used as last resort."""
        deal = Deal(
            id="d3",
            title="Test",
            current_price=10.0,
            raw_metadata={"cheapshark_deal_id": "123"},
        )
        result = TopGamesService._resolve_game_id(deal)
        assert result == "cheapshark:123"

    def test_no_id_returns_none(self) -> None:
        """Verify None when deal has no identifiers."""
        deal = Deal(id="d4", title="Test", current_price=10.0)
        result = TopGamesService._resolve_game_id(deal)
        assert result is None

    def test_none_steam_app_id_falls_back(self) -> None:
        """Verify steam_app_id=None is ignored."""
        deal = Deal(
            id="d5",
            title="Test",
            current_price=10.0,
            raw_metadata={"steam_app_id": None, "itad_plain_id": "hollow"},
        )
        result = TopGamesService._resolve_game_id(deal)
        assert result == "itad:hollow"


@pytest.mark.unit
class TestTopGamesServiceFreshness:
    """_freshness_score behavior."""

    def test_trending_gets_full_score(self) -> None:
        """Verify trending games get freshness score of 1.0."""
        signal = _signal(is_trending=True)
        score = TopGamesService._freshness_score(signal, None)
        assert score == 1.0

    def test_non_trending_gets_baseline(self) -> None:
        """Verify non-trending games get baseline freshness."""
        signal = _signal(is_trending=False)
        score = TopGamesService._freshness_score(signal, None)
        assert score == 0.3
