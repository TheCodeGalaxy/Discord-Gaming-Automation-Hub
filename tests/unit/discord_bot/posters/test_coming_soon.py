"""Tests for ComingSoonPoster."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from gaming_hub.discord_bot.posters.coming_soon import ComingSoonPoster
from gaming_hub.services.new_releases_service import NewReleasesResult


@pytest.mark.unit
class TestComingSoonPoster:
    """ComingSoonPoster behavior."""

    @pytest.mark.asyncio
    async def test_build_content_returns_embeds(self) -> None:
        """Verify _build_content returns embeds when releases exist."""
        bot = MagicMock()
        service = AsyncMock()
        game = MagicMock()
        game.title = "Monthly Release"
        game.release_date = MagicMock()
        game.release_date.strftime.return_value = "Jul 15, 2026"
        game.genres = ["Action"]
        game.cover_url = None
        result = NewReleasesResult(games=[game], total=1)
        service.get_current_month.return_value = result
        bot._container.resolve.return_value = service

        poster = ComingSoonPoster(bot, 12345)
        embeds = await poster._build_content({})
        assert len(embeds) == 1
        assert "Monthly Release" in embeds[0].title

    @pytest.mark.asyncio
    async def test_empty_result_returns_informative_embed(self) -> None:
        """Verify an informative embed when no releases this month."""
        bot = MagicMock()
        service = AsyncMock()
        service.get_current_month.return_value = NewReleasesResult(games=[], total=0)
        bot._container.resolve.return_value = service

        poster = ComingSoonPoster(bot, 12345)
        embeds = await poster._build_content({})
        assert len(embeds) == 1
        assert "No Releases Scheduled" in embeds[0].title

    @pytest.mark.asyncio
    async def test_passes_limit_to_service(self) -> None:
        """Verify job_data limit is forwarded to the service."""
        bot = MagicMock()
        service = AsyncMock()
        result = NewReleasesResult(games=[], total=0)
        service.get_current_month.return_value = result
        bot._container.resolve.return_value = service

        poster = ComingSoonPoster(bot, 12345)
        await poster._build_content({"limit": 5})
        service.get_current_month.assert_awaited_once_with(limit=5)

    @pytest.mark.asyncio
    async def test_capped_at_limit(self) -> None:
        """Verify at most ``limit`` embeds are returned."""
        bot = MagicMock()
        service = AsyncMock()
        games = [MagicMock(title=f"Game {i}") for i in range(15)]
        result = NewReleasesResult(games=games, total=15)
        service.get_current_month.return_value = result
        bot._container.resolve.return_value = service

        poster = ComingSoonPoster(bot, 12345)
        embeds = await poster._build_content({"limit": 5})
        assert len(embeds) == 5
