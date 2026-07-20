"""Unit tests for the /discount command cog."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from gaming_hub.core.enums import StoreName
from gaming_hub.discord_bot.cogs.commands.discount_cog import DiscountCog
from gaming_hub.models.domain.deal import Deal
from gaming_hub.services.discount_service import DiscountResult

from .conftest import resolved


@pytest.mark.unit
class TestDiscountCog:
    """Discount command behavior."""

    @pytest.mark.asyncio
    async def test_discount_responds_with_pagination(
        self, bot: MagicMock, interaction: MagicMock,
    ) -> None:
        """/discount responds with embeds and a paginator when deals exist."""
        deal = Deal(
            id="d1",
            title="Big Deal",
            store=StoreName.Steam,
            current_price=4.99,
            original_price=49.99,
            discount_percent=90,
            provider_names=["cheapshark"],
        )
        service = MagicMock()
        service.get_crazy_discounts = AsyncMock(
            return_value=DiscountResult(deals=[deal], total=1),
        )
        resolved(bot, service)
        cog = DiscountCog(bot)

        await cog.discount.callback(cog, interaction)

        service.get_crazy_discounts.assert_awaited_once()
        interaction.response.defer.assert_awaited_once()
        _, kwargs = interaction.followup.send.call_args
        assert kwargs["embed"] is not None
        assert kwargs["view"] is not None

    @pytest.mark.asyncio
    async def test_discount_empty_responds_ephemeral(
        self, bot: MagicMock, interaction: MagicMock,
    ) -> None:
        """Empty discounts produce an ephemeral message."""
        service = MagicMock()
        service.get_crazy_discounts = AsyncMock(return_value=DiscountResult())
        resolved(bot, service)
        cog = DiscountCog(bot)

        await cog.discount.callback(cog, interaction)

        _, kwargs = interaction.followup.send.call_args
        assert kwargs["ephemeral"] is True
