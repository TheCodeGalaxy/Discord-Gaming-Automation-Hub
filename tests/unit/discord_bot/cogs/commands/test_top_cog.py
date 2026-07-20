"""Unit tests for the /top command cog."""

from __future__ import annotations

from datetime import UTC, date, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from gaming_hub.discord_bot.cogs.commands.top_cog import TopCog
from gaming_hub.services.top_games_service import (
    GameSignal,
    ScoredGame,
    TopGamesResult,
)

from .conftest import resolved


def _make_result() -> TopGamesResult:
    game1 = ScoredGame(
        game_id="steam:730",
        title="Counter-Strike 2",
        score=8.5,
        signals=GameSignal(
            game_id="steam:730",
            title="Counter-Strike 2",
            discount_percent=50.0,
            review_score=92.0,
        ),
    )
    game2 = ScoredGame(
        game_id="steam:570",
        title="Dota 2",
        score=7.2,
        signals=GameSignal(
            game_id="steam:570",
            title="Dota 2",
            discount_percent=0.0,
            review_score=85.0,
        ),
    )
    return TopGamesResult(
        games=[game1, game2],
        total=2,
        week_ending=date(2026, 7, 25),
        computed_at=datetime(2026, 7, 18, 14, 0, 0, tzinfo=UTC),
    )


@pytest.mark.unit
class TestTopCog:
    """Top command behavior."""

    def test_init_resolves_service(self, bot: MagicMock) -> None:
        """Cog resolves TopGamesService via the container."""
        service = MagicMock()
        resolved(bot, service)
        cog = TopCog(bot)
        assert cog._top_games_service is service

    @pytest.mark.asyncio
    async def test_top_responds_with_pagination(
        self, bot: MagicMock, interaction: MagicMock,
    ) -> None:
        """/top responds with embeds and a paginator when games exist."""
        result = _make_result()
        service = MagicMock()
        service.get_weekly_top = AsyncMock(return_value=result)
        resolved(bot, service)
        cog = TopCog(bot)

        await cog.top.callback(cog, interaction)

        service.get_weekly_top.assert_awaited_once()
        interaction.response.defer.assert_awaited_once()
        _, kwargs = interaction.followup.send.call_args
        assert kwargs["embed"] is not None
        assert kwargs["view"] is not None

    @pytest.mark.asyncio
    async def test_top_empty_responds_ephemeral(
        self, bot: MagicMock, interaction: MagicMock,
    ) -> None:
        """No top games produce an ephemeral message."""
        service = MagicMock()
        service.get_weekly_top = AsyncMock(
            return_value=TopGamesResult(
                games=[], total=0,
                week_ending=date(2026, 7, 25),
                computed_at=datetime(2026, 7, 18, 14, 0, 0, tzinfo=UTC),
            ),
        )
        resolved(bot, service)
        cog = TopCog(bot)

        await cog.top.callback(cog, interaction)

        _, kwargs = interaction.followup.send.call_args
        assert kwargs["ephemeral"] is True
