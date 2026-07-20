"""Tests for MajorUpdatesPoster."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from gaming_hub.discord_bot.posters.major_updates import MajorUpdatesPoster
from gaming_hub.services.major_updates_service import GameUpdate, MajorUpdatesResult


@pytest.mark.unit
class TestMajorUpdatesPoster:
    """MajorUpdatesPoster behavior."""

    @pytest.mark.asyncio
    async def test_build_content_returns_embeds(self) -> None:
        """Verify _build_content returns embeds when updates exist."""
        bot = MagicMock()
        service = AsyncMock()
        update = GameUpdate(
            app_id=440,
            title="TF2 — Major Update Released",
            game_name="Team Fortress 2",
            update_title="Major Update Released",
            url="https://steamcommunity.com/games/440/announcements/detail/123",
            date=datetime(2026, 7, 15),
            snippet="A major content update has been released.",
        )
        result = MajorUpdatesResult(updates=[update], total=1)
        service.get_major_updates.return_value = result
        bot._container.resolve.return_value = service

        poster = MajorUpdatesPoster(bot, 12345)
        embeds = await poster._build_content({})
        assert len(embeds) == 1
        assert "Team Fortress 2" in embeds[0].title

    @pytest.mark.asyncio
    async def test_empty_result_returns_informative_embed(self) -> None:
        """Verify an informative embed when no updates found."""
        bot = MagicMock()
        service = AsyncMock()
        service.get_major_updates.return_value = MajorUpdatesResult(updates=[], total=0)
        bot._container.resolve.return_value = service

        poster = MajorUpdatesPoster(bot, 12345)
        embeds = await poster._build_content({})
        assert len(embeds) == 1
        assert "No Major Updates" in embeds[0].title

    @pytest.mark.asyncio
    async def test_passes_limit_to_service(self) -> None:
        """Verify job_data limit is forwarded to the service."""
        bot = MagicMock()
        service = AsyncMock()
        service.get_major_updates.return_value = MajorUpdatesResult(updates=[], total=0)
        bot._container.resolve.return_value = service

        poster = MajorUpdatesPoster(bot, 12345)
        await poster._build_content({"limit": 3})
        service.get_major_updates.assert_awaited_once_with(limit=3)

    @pytest.mark.asyncio
    async def test_capped_at_limit(self) -> None:
        """Verify at most ``limit`` embeds are returned."""
        bot = MagicMock()
        service = AsyncMock()
        updates = [GameUpdate(app_id=i, title=f"Update {i}", game_name="G", update_title=f"Update {i}", url="", date=datetime(2026, 7, 1 + i % 28), snippet="") for i in range(15)]
        result = MajorUpdatesResult(updates=updates, total=15)
        service.get_major_updates.return_value = result
        bot._container.resolve.return_value = service

        poster = MajorUpdatesPoster(bot, 12345)
        embeds = await poster._build_content({"limit": 5})
        assert len(embeds) == 5
