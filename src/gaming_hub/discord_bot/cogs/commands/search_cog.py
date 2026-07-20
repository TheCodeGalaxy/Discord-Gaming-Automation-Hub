"""/search command cog.
"""

from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from gaming_hub.discord_bot.bot import GamingHubBot
from gaming_hub.discord_bot.utils.embed_builder import build_game_search_embeds
from gaming_hub.discord_bot.utils.pagination import PaginatorView
from gaming_hub.services.search_service import SearchService


class SearchCog(commands.Cog):
    def __init__(self, bot: GamingHubBot):
        self.bot = bot
        self._search_service = bot._container.resolve(SearchService)

    @app_commands.command(
        name="search",
        description="Search for game deals by title",
    )
    @app_commands.describe(
        query="Game title to search for",
    )
    async def search(
        self,
        interaction: discord.Interaction,
        query: str,
    ):
        from gaming_hub.models.dto.request import SearchRequest
        await interaction.response.defer(ephemeral=False)
        request = SearchRequest(query=query, limit=10)
        result = await self._search_service.search(request)
        if not result.games:
            await interaction.followup.send("No games found for that query.", ephemeral=True)
            return

        embeds = build_game_search_embeds(result.games)
        paginator = PaginatorView(embeds, interaction.user.id)
        await interaction.followup.send(embed=embeds[0], view=paginator)

    @search.autocomplete("query")
    async def search_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        if not current or len(current) < 2:
            return []
        suggestions = await self._search_service.autocomplete(current, limit=10)
        return [app_commands.Choice(name=s.label, value=s.label) for s in suggestions]


async def setup(bot: GamingHubBot) -> None:
    await bot.add_cog(SearchCog(bot))
