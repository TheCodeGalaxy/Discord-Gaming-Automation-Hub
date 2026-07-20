"""/top command cog.
"""

from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from gaming_hub.discord_bot.bot import GamingHubBot
from gaming_hub.discord_bot.utils.embed_builder import build_top_games_embeds
from gaming_hub.discord_bot.utils.pagination import PaginatorView
from gaming_hub.services.top_games_service import TopGamesService


class TopCog(commands.Cog):
    def __init__(self, bot: GamingHubBot):
        self.bot = bot
        self._top_games_service = bot._container.resolve(TopGamesService)

    @app_commands.command(
        name="top",
        description="List top-rated games",
    )
    async def top(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=False)
        result = await self._top_games_service.get_weekly_top()
        if not result.games:
            await interaction.followup.send("No top games available right now.", ephemeral=True)
            return

        embeds = build_top_games_embeds(result.games)
        paginator = PaginatorView(embeds, interaction.user.id)
        await interaction.followup.send(embed=embeds[0], view=paginator)


async def setup(bot: GamingHubBot) -> None:
    await bot.add_cog(TopCog(bot))
