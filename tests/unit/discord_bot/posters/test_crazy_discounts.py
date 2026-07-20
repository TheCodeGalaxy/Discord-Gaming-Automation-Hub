"""Tests for CrazyDiscountsPoster."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from gaming_hub.discord_bot.posters.crazy_discounts import CrazyDiscountsPoster
from gaming_hub.services.discount_service import DiscountResult


@pytest.mark.unit
class TestCrazyDiscountsPoster:
    """CrazyDiscountsPoster behavior."""

    @pytest.mark.asyncio
    async def test_build_content_returns_embeds(self) -> None:
        """Verify _build_content returns embeds when deals exist."""
        bot = MagicMock()
        service = AsyncMock()
        deal = MagicMock()
        deal.title = "Cheap Game"
        deal.current_price = 4.99
        deal.original_price = 49.99
        deal.discount_percent = 90.0
        deal.store = "Steam"
        deal.store_url = "https://store.steampowered.com"
        deal.deal_ends_at = None
        service.get_crazy_discounts.return_value = DiscountResult(deals=[deal])
        bot._container.resolve.return_value = service

        poster = CrazyDiscountsPoster(bot, 12345)
        embeds = await poster._build_content({})
        assert len(embeds) == 1
        assert "Cheap Game" in embeds[0].title

    @pytest.mark.asyncio
    async def test_empty_result_returns_empty_list(self) -> None:
        """Verify no embeds when no deals."""
        bot = MagicMock()
        service = AsyncMock()
        service.get_crazy_discounts.return_value = DiscountResult(deals=[])
        bot._container.resolve.return_value = service

        poster = CrazyDiscountsPoster(bot, 12345)
        embeds = await poster._build_content({})
        assert embeds == []

    @pytest.mark.asyncio
    async def test_capped_at_ten_embeds(self) -> None:
        """Verify at most 10 embeds are returned."""
        bot = MagicMock()
        service = AsyncMock()
        deals = [
            MagicMock(title=f"Deal {i}", original_price=49.99, current_price=9.99, discount_percent=80.0,
                      store="Steam", store_url="https://store.steampowered.com", deal_ends_at=None)
            for i in range(15)
        ]
        service.get_crazy_discounts.return_value = DiscountResult(deals=deals)
        bot._container.resolve.return_value = service

        poster = CrazyDiscountsPoster(bot, 12345)
        embeds = await poster._build_content({})
        assert len(embeds) == 10
