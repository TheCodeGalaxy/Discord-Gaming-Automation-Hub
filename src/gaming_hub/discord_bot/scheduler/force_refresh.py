"""One-time monthly force refresh utility.

Deletes existing July 2026 Discord messages for the two monthly poster
channels and republishes them using the corrected collectors.

Only activates when ``MONTHLY_FORCE_REFRESH=true`` in the environment.
Automatically self-resets per startup so it never double-publishes
the same channel in one session.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import discord

from gaming_hub.discord_bot.scheduler.channel_scheduler import PublicationRepository

if TYPE_CHECKING:
    from gaming_hub.config.models import Settings
    from gaming_hub.discord_bot.bot import GamingHubBot
    from gaming_hub.discord_bot.posters import PosterRegistry

logger = logging.getLogger(__name__)

_MONTHLY_PERIOD = "2026-07"
_MONTHLY_CHANNELS = ("post_coming_soon", "post_major_updates")
_refreshed: set[str] = set()


async def force_refresh_monthly(
    bot: GamingHubBot,
    settings: Settings,
    poster_registry: PosterRegistry,
) -> None:
    """Force-refresh July 2026 posts for the two monthly channels.

    Checks ``settings.monthly_force_refresh``. When true, reads the stored
    publication record for each monthly channel, deletes the old Discord
    message, runs the poster's collector, publishes fresh embeds, and
    updates the stored message ID while keeping the period as ``2026-07``.

    Each channel is tracked in a module-level ``_refreshed`` set so it
    only runs once per process lifetime — even if called multiple times.
    """
    if not settings.monthly_force_refresh:
        return

    logger.info("MONTHLY_FORCE_REFRESH enabled — force-refreshing July 2026 posts")

    repo = PublicationRepository(settings.database_dir)
    await repo.init()

    for channel_name in _MONTHLY_CHANNELS:
        if channel_name in _refreshed:
            logger.info("%s: already refreshed this session — skipped", channel_name)
            continue

        record = await repo.get(channel_name)
        if record is None or record["period"] != _MONTHLY_PERIOD:
            logger.info(
                "%s: no July 2026 record found (period=%s) — skipping",
                channel_name,
                record["period"] if record else "None",
            )
            continue

        old_message_id = record.get("message_id")

        poster = poster_registry.get(channel_name)
        if poster is None:
            logger.warning("%s: poster not registered — cannot force-refresh", channel_name)
            continue

        if old_message_id is not None:
            await _delete_message(bot, poster.channel_id, old_message_id, channel_name)

        result = await poster.execute()
        new_message_id = result.message_ids[0] if result.message_ids else None
        await repo.upsert(channel_name, _MONTHLY_PERIOD, new_message_id)

        _refreshed.add(channel_name)

        if result.success:
            logger.info(
                "%s: force-refreshed with %d embed(s), message_id=%s",
                channel_name,
                result.embed_count,
                new_message_id,
            )
        else:
            logger.warning(
                "%s: force-refresh failed — %s",
                channel_name,
                result.error,
            )

    logger.info("MONTHLY_FORCE_REFRESH complete for this session")


async def _delete_message(
    bot: GamingHubBot,
    channel_id: int,
    message_id: int,
    channel_name: str,
) -> None:
    """Delete the old Discord message by channel and message ID."""
    try:
        channel = bot.get_channel(channel_id) or await bot.fetch_channel(channel_id)
        if not isinstance(channel, (discord.TextChannel, discord.Thread)):
            logger.debug("%s: channel %d is not a text channel", channel_name, channel_id)
            return
        msg = await channel.fetch_message(message_id)
        await msg.delete()
        logger.info("%s: deleted old message %d", channel_name, message_id)
    except Exception:
        logger.debug(
            "%s: could not delete message %d (may be deleted already)",
            channel_name,
            message_id,
        )
