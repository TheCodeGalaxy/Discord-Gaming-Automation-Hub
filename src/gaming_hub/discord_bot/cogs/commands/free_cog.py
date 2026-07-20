"""/free command cog.
"""

from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from gaming_hub.discord_bot.bot import GamingHubBot
from gaming_hub.discord_bot.utils.embed_builder import build_free_embeds
from gaming_hub.discord_bot.utils.pagination import PaginatorView
from gaming_hub.services.free_games_service import FreeGamesService


class FreeCog(commands.Cog):
    def __init__(self, bot: GamingHubBot):
        self.bot = bot
        self._free_games_service = bot._container.resolve(FreeGamesService)

    @app_commands.command(
        name="free",
        description="List current free games",
    )
    async def free(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=False)
        result = await self._free_games_service.get_current()
        if not result.current:
            await interaction.followup.send("No free games available right now.", ephemeral=True)
            return

        embeds = build_free_embeds(result.current)
        paginator = PaginatorView(embeds, interaction.user.id)
        await interaction.followup.send(embed=embeds[0], view=paginator)


async def setup(bot: GamingHubBot) -> None:
    await bot.add_cog(FreeCog(bot))
