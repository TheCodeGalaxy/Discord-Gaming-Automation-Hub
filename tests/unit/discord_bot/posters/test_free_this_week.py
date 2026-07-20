"""Tests for FreeThisWeekPoster."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from gaming_hub.discord_bot.posters.free_this_week import FreeThisWeekPoster
from gaming_hub.services.free_games_service import FreeGamesResult


@pytest.mark.unit
class TestFreeThisWeekPoster:
    """FreeThisWeekPoster behavior."""

    @pytest.mark.asyncio
    async def test_build_content_returns_embeds(self) -> None:
        """Verify _build_content returns embeds when games exist."""
        bot = MagicMock()
        service = AsyncMock()
        game = MagicMock()
        game.title = "Free Game"
        game.free_until = None
        game.cover_url = None
        service.get_current.return_value = FreeGamesResult(current=[game])
        bot._container.resolve.return_value = service

        poster = FreeThisWeekPoster(bot, 12345)
        embeds = await poster._build_content({})
        assert len(embeds) == 1
        assert embeds[0].title == "Free Game"

    @pytest.mark.asyncio
    async def test_empty_result_returns_empty_list(self) -> None:
        """Verify no embeds when no games are free."""
        bot = MagicMock()
        service = AsyncMock()
        service.get_current.return_value = FreeGamesResult(current=[])
        bot._container.resolve.return_value = service

        poster = FreeThisWeekPoster(bot, 12345)
        embeds = await poster._build_content({})
        assert embeds == []

    @pytest.mark.asyncio
    async def test_capped_at_ten_embeds(self) -> None:
        """Verify at most 10 embeds are returned."""
        bot = MagicMock()
        service = AsyncMock()
        games = [MagicMock(title=f"Game {i}", free_until=None, cover_url=None) for i in range(15)]
        service.get_current.return_value = FreeGamesResult(current=games)
        bot._container.resolve.return_value = service

        poster = FreeThisWeekPoster(bot, 12345)
        embeds = await poster._build_content({})
        assert len(embeds) == 10
