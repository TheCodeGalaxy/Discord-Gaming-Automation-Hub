"""Embed formatting helpers for Discord commands.
"""

from __future__ import annotations

import discord

from gaming_hub.models.domain import Deal, Game
from gaming_hub.services.top_games_service import ScoredGame


def build_search_embeds(deals: list[Deal]) -> list[discord.Embed]:
    """Build embeds for search results from deals."""
    embeds = []
    for deal in deals:
        embed = discord.Embed(
            title=deal.title,
            description="Game deal",
            color=discord.Color.green(),
            url=deal.store_url
        )
        embed.add_field(name="Price", value=f"${deal.current_price:.2f}", inline=True)
        embed.add_field(name="Discount", value=f"{deal.discount_percent:.0f}%", inline=True)
        embed.add_field(name="Store", value=str(deal.store), inline=True)
        embeds.append(embed)
    return embeds


def build_game_search_embeds(games: list[Game]) -> list[discord.Embed]:
    """Build embeds for game search results."""
    embeds = []
    for game in games:
        embed = discord.Embed(
            title=game.title,
            description=game.short_description or "Game search result",
            color=discord.Color.blue(),
            url=game.provider_url
        )
        embed.add_field(name="Provider", value=game.provider_name, inline=True)
        if game.steam_app_id:
            embed.add_field(name="Steam App ID", value=str(game.steam_app_id), inline=True)
        if game.genres:
            embed.add_field(name="Genres", value=", ".join(game.genres[:3]), inline=True)
        if game.release_date:
            embed.add_field(name="Release Date", value=game.release_date.strftime("%Y-%m-%d"), inline=True)
        if game.cover_url:
            embed.set_thumbnail(url=str(game.cover_url))
        embeds.append(embed)
    return embeds


def build_free_embeds(free_games: list[Game]) -> list[discord.Embed]:
    """Build embeds for free games."""
    embeds = []
    for game in free_games:
        embed = discord.Embed(
            title=game.title,
            description=game.short_description or "Free game",
            color=discord.Color.blue(),
            url=game.provider_url
        )
        embed.add_field(name="Store", value=game.provider_name, inline=True)
        if game.free_until:
            embed.add_field(name="Ends At", value=game.free_until.strftime("%Y-%m-%d"), inline=True)
        if game.cover_url:
            embed.set_thumbnail(url=str(game.cover_url))
        embeds.append(embed)
    return embeds


def build_discount_embeds(discounts: list[Deal]) -> list[discord.Embed]:
    """Build embeds for top discounts."""
    embeds = []
    for deal in discounts:
        embed = discord.Embed(
            title=deal.title,
            description="Game discount",
            color=discord.Color.green(),
            url=deal.store_url
        )
        if deal.original_price:
            embed.add_field(name="Original Price", value=f"${deal.original_price:.2f}", inline=True)
        embed.add_field(name="Discount", value=f"{deal.discount_percent:.0f}%", inline=True)
        embed.add_field(name="Current Price", value=f"${deal.current_price:.2f}", inline=True)
        embeds.append(embed)
    return embeds


def build_surprise_embed(game: Game) -> discord.Embed:
    """Build embed for a random game."""
    embed = discord.Embed(
        title=game.title,
        description=game.short_description or "Random game discovery",
        color=discord.Color.purple(),
        url=game.provider_url
    )
    if game.steam_review_score:
        embed.add_field(name="Steam Score", value=f"{game.steam_review_score:.0f}/100", inline=True)
    if game.genres:
        embed.add_field(name="Genres", value=", ".join(game.genres[:3]), inline=True)
    if game.cover_url:
        embed.set_thumbnail(url=str(game.cover_url))
    return embed


def build_new_releases_embeds(releases: list[Game]) -> list[discord.Embed]:
    """Build rich embeds for new releases (last-3-months games)."""
    embeds = []
    for release in releases:
        desc = (release.short_description or release.description or "")
        if desc:
            desc = (desc[:250] + "\u2026") if len(desc) > 250 else desc
        embed = discord.Embed(
            title=release.title,
            description=desc or "New release",
            color=discord.Color.gold(),
            url=release.provider_url,
        )
        if release.release_date:
            embed.add_field(
                name="Release Date",
                value=release.release_date.strftime("%b %d, %Y"),
                inline=True,
            )
        if release.platforms:
            embed.add_field(
                name="Platforms",
                value=", ".join(release.platforms[:5]),
                inline=True,
            )
        if release.genres:
            embed.add_field(
                name="Genres",
                value=", ".join(release.genres[:4]),
                inline=True,
            )
        if release.developers:
            embed.add_field(
                name="Developer",
                value=release.developers[0],
                inline=True,
            )
        if release.cover_url:
            embed.set_thumbnail(url=str(release.cover_url))
        if release.steam_app_id:
            embed.add_field(
                name="Steam",
                value=f"[Store Page](https://store.steampowered.com/app/{release.steam_app_id})",
                inline=False,
            )
        embeds.append(embed)
    return embeds


def build_top_games_embeds(games: list[ScoredGame]) -> list[discord.Embed]:
    """Build embeds for top games."""
    embeds = []
    for rank, game in enumerate(games, 1):
        embed = discord.Embed(
            title=game.title,
            description=f"Score: {game.score:.2f}",
            color=discord.Color.gold(),
        )
        embed.add_field(name="Rank", value=f"#{rank}", inline=True)
        if game.signals.review_score:
            embed.add_field(name="Review Score", value=f"{game.signals.review_score:.0f}/100", inline=True)
        if game.signals.discount_percent:
            embed.add_field(name="Discount", value=f"{game.signals.discount_percent:.0f}%", inline=True)
        embeds.append(embed)
    return embeds


def build_help_embed() -> discord.Embed:
    """Build embed for /help command."""
    embed = discord.Embed(
        title="Gaming Hub Commands",
        description="Here are the available commands:",
        color=discord.Color.blue()
    )
    embed.add_field(
        name="/search",
        value="Search for game deals by title. Usage: `/search <query>`",
        inline=False
    )
    embed.add_field(
        name="/free",
        value="List current free games. Usage: `/free`",
        inline=False
    )
    embed.add_field(
        name="/discount",
        value="List top game discounts. Usage: `/discount`",
        inline=False
    )
    embed.add_field(
        name="/surprise",
        value="Get a random game. Usage: `/surprise`",
        inline=False
    )
    embed.add_field(
        name="/new",
        value="List recent game releases. Usage: `/new`",
        inline=False
    )
    embed.add_field(
        name="/top",
        value="List top-rated games. Usage: `/top`",
        inline=False
    )
    return embed
