"""Unit tests for the /search command cog."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from gaming_hub.core.enums import StoreName
from gaming_hub.discord_bot.cogs.commands.search_cog import SearchCog
from gaming_hub.models.domain.deal import Deal
from gaming_hub.models.domain.game import Game
from gaming_hub.services.search_service import SearchResult

from .conftest import resolved


def _make_result() -> SearchResult:
    game = Game(id="1", title="Cyberpunk 2077", provider_name="cheapshark")
    deal = Deal(
        id="d1",
        title="Cyberpunk 2077",
        store=StoreName.Steam,
        current_price=29.99,
        original_price=59.99,
        discount_percent=50,
        provider_names=["cheapshark"],
    )
    return SearchResult(games=[game], deals=[deal], total_games=1, total_deals=1)


@pytest.mark.unit
class TestSearchCog:
    """Search command behavior."""

    def test_init_resolves_service(self, bot: MagicMock) -> None:
        """Cog resolves SearchService via the container."""
        service = MagicMock()
        resolved(bot, service)
        cog = SearchCog(bot)
        assert cog._search_service is service

    @pytest.mark.asyncio
    async def test_search_returns_embeds_with_pagination(
        self, bot: MagicMock, interaction: MagicMock,
    ) -> None:
        """Search responds with the first embed and a PaginatorView."""
        service = MagicMock()
        service.search = AsyncMock(return_value=_make_result())
        resolved(bot, service)
        cog = SearchCog(bot)

        await cog.search.callback(cog, interaction, "cyberpunk")

        service.search.assert_awaited_once()
        interaction.response.defer.assert_awaited_once()
        _, kwargs = interaction.followup.send.call_args
        assert kwargs["embed"] is not None
        assert kwargs["view"] is not None

    @pytest.mark.asyncio
    async def test_search_empty_responds_ephemeral(
        self, bot: MagicMock, interaction: MagicMock,
    ) -> None:
        """Empty results produce an ephemeral 'no deals' message."""
        service = MagicMock()
        service.search = AsyncMock(return_value=SearchResult())
        resolved(bot, service)
        cog = SearchCog(bot)

        await cog.search.callback(cog, interaction, "zzzzz")

        _, kwargs = interaction.followup.send.call_args
        assert kwargs["ephemeral"] is True

    @pytest.mark.asyncio
    async def test_autocomplete_returns_titles(self, bot: MagicMock) -> None:
        """Autocomplete returns choices after >=2 chars."""
        from gaming_hub.services.search_service import AutocompleteItem

        service = MagicMock()
        service.autocomplete = AsyncMock(
            return_value=[
                AutocompleteItem(label="Cyberpunk 2077", value="1", provider="cheapshark"),
            ],
        )
        resolved(bot, service)
        cog = SearchCog(bot)
        interaction = MagicMock()
        interaction.user = MagicMock()

        result = await cog.search_autocomplete(interaction, "cy")

        assert isinstance(result, list)
        assert result[0].name == "Cyberpunk 2077"
        service.autocomplete.assert_awaited_once_with("cy", limit=10)

    @pytest.mark.asyncio
    async def test_autocomplete_short_input_empty(self, bot: MagicMock) -> None:
        """Autocomplete returns [] for <2 chars."""
        resolved(bot, MagicMock())
        cog = SearchCog(bot)
        interaction = MagicMock()
        interaction.user = MagicMock()
        assert await cog.search_autocomplete(interaction, "c") == []
