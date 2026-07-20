"""Poster factory — wire posters to services and channels at startup.

Reads channel IDs from ``Settings`` and registers each poster in the
``PosterRegistry`` keyed by action name.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from gaming_hub.discord_bot.posters import PosterRegistry
from gaming_hub.discord_bot.posters.coming_soon import ComingSoonPoster
from gaming_hub.discord_bot.posters.crazy_discounts import CrazyDiscountsPoster
from gaming_hub.discord_bot.posters.free_this_week import FreeThisWeekPoster
from gaming_hub.discord_bot.posters.major_updates import MajorUpdatesPoster
from gaming_hub.discord_bot.posters.top_this_week import TopThisWeekPoster

if TYPE_CHECKING:
    from gaming_hub.config.models import Settings
    from gaming_hub.discord_bot.bot import GamingHubBot

logger = logging.getLogger(__name__)

_CHANNEL_MAP: dict[str, str] = {
    "post_free_this_week": "discord_free_games_channel_id",
    "post_crazy_discounts": "discord_crazy_discounts_channel_id",
    "post_top_this_week": "discord_top_games_channel_id",
    "post_major_updates": "discord_major_updates_channel_id",
    "post_coming_soon": "discord_coming_soon_channel_id",
}

_POSTER_CLASSES: dict[str, type] = {
    "post_free_this_week": FreeThisWeekPoster,
    "post_crazy_discounts": CrazyDiscountsPoster,
    "post_top_this_week": TopThisWeekPoster,
    "post_major_updates": MajorUpdatesPoster,
    "post_coming_soon": ComingSoonPoster,
}


def create_poster_registry(bot: GamingHubBot, settings: Settings) -> PosterRegistry:
    """Build and return a fully-wired ``PosterRegistry``.

    Args:
        bot: The ``GamingHubBot`` instance (needed by each poster).
        settings: Application settings with ``discord_*_channel_id`` fields.

    Returns:
        A ``PosterRegistry`` with all 5 posters registered.
    """
    registry = PosterRegistry()
    for action, channel_field in _CHANNEL_MAP.items():
        channel_id = getattr(settings, channel_field, None)
        if not channel_id:
            logger.warning("Skipping poster %s: %s not configured", action, channel_field)
            continue
        poster_class = _POSTER_CLASSES[action]
        poster = poster_class(bot, int(channel_id))
        registry.register(action, poster)
        logger.info("Registered poster: %s -> channel %s", action, channel_id)
    return registry
