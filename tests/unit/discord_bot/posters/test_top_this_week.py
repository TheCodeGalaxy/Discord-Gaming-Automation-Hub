"""Tests for TopThisWeekPoster."""

from __future__ import annotations

from datetime import date, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from gaming_hub.discord_bot.posters.top_this_week import TopThisWeekPoster
from gaming_hub.services.top_games_service import (
    GameSignal,
    ScoredGame,
    TopGamesResult,
)


def _scored_game(title: str, score: float) -> ScoredGame:
    return ScoredGame(
        game_id=title.lower().replace(" ", "-"),
        title=title,
        score=score,
        signals=GameSignal(
            game_id=title.lower().replace(" ", "-"),
            title=title,
        ),
    )


@pytest.mark.unit
class TestTopThisWeekPoster:
    """TopThisWeekPoster behavior."""

    @pytest.mark.asyncio
    async def test_build_content_returns_embeds(self) -> None:
        """Verify _build_content returns embeds when games exist."""
        bot = MagicMock()
        service = AsyncMock()
        result = TopGamesResult(
            games=[_scored_game("Top Game", 95.0)],
            total=1,
            week_ending=date.today(),
            computed_at=datetime.now(),
        )
        service.get_weekly_top.return_value = result
        bot._container.resolve.return_value = service

        poster = TopThisWeekPoster(bot, 12345)
        embeds = await poster._build_content({})
        assert len(embeds) == 1
        assert "Top Game" in embeds[0].title
        assert "95.00" in embeds[0].description

    @pytest.mark.asyncio
    async def test_empty_result_returns_empty_list(self) -> None:
        """Verify no embeds when no top games."""
        bot = MagicMock()
        service = AsyncMock()
        result = TopGamesResult(
            games=[],
            total=0,
            week_ending=date.today(),
            computed_at=datetime.now(),
        )
        service.get_weekly_top.return_value = result
        bot._container.resolve.return_value = service

        poster = TopThisWeekPoster(bot, 12345)
        embeds = await poster._build_content({})
        assert embeds == []

    @pytest.mark.asyncio
    async def test_rank_is_included(self) -> None:
        """Verify rank field is present and sequential."""
        bot = MagicMock()
        service = AsyncMock()
        result = TopGamesResult(
            games=[
                _scored_game("Game One", 95.0),
                _scored_game("Game Two", 90.0),
            ],
            total=2,
            week_ending=date.today(),
            computed_at=datetime.now(),
        )
        service.get_weekly_top.return_value = result
        bot._container.resolve.return_value = service

        poster = TopThisWeekPoster(bot, 12345)
        embeds = await poster._build_content({})
        assert len(embeds) == 2
        assert "#1" in str(embeds[0].fields)
        assert "#2" in str(embeds[1].fields)
