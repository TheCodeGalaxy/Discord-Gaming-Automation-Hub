"""Channel-based startup scheduler with SQLite persistence.

Each channel has a period type (weekly/monthly). On bot startup the scheduler
checks whether the current period has already been published. If not, it
publishes immediately. The publication record survives restarts.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

import aiosqlite
import discord

if TYPE_CHECKING:
    from gaming_hub.config.models import Settings
    from gaming_hub.discord_bot.bot import GamingHubBot
    from gaming_hub.discord_bot.posters import PosterRegistry
    from gaming_hub.discord_bot.posters.base import BasePoster

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Period type
# ---------------------------------------------------------------------------

PeriodType = Literal["weekly", "monthly"]


def current_period(period_type: PeriodType) -> str:
    """Return the current ISO period string.

    Weekly:   "2026-W29"
    Monthly:  "2026-07"
    """
    now = datetime.now(UTC)
    if period_type == "weekly":
        iso = now.isocalendar()
        return f"{iso[0]}-W{iso[1]:02d}"
    return now.strftime("%Y-%m")


# ---------------------------------------------------------------------------
# Channel schedule configuration
# ---------------------------------------------------------------------------

@dataclass
class ChannelSchedule:
    """Schedule definition for one poster channel."""

    action: str
    period_type: PeriodType
    description: str


CHANNEL_SCHEDULES: dict[str, ChannelSchedule] = {
    "post_free_this_week": ChannelSchedule(
        action="post_free_this_week",
        period_type="weekly",
        description="Free games — every Friday 00:00 UTC",
    ),
    "post_crazy_discounts": ChannelSchedule(
        action="post_crazy_discounts",
        period_type="weekly",
        description="Crazy discounts — every Friday 00:00 UTC",
    ),
    "post_top_this_week": ChannelSchedule(
        action="post_top_this_week",
        period_type="weekly",
        description="Top games — every Friday 00:00 UTC",
    ),
    "post_coming_soon": ChannelSchedule(
        action="post_coming_soon",
        period_type="monthly",
        description="Coming soon — day 1 of month 00:00 UTC",
    ),
    "post_major_updates": ChannelSchedule(
        action="post_major_updates",
        period_type="monthly",
        description="Major updates — day 1 of month 00:00 UTC",
    ),
}


# ---------------------------------------------------------------------------
# SQLite repository
# ---------------------------------------------------------------------------

_DB_FILENAME = "scheduler.db"

# One-time migration constants — marks that July 2026 monthly channel
# records (created by the old placeholder logic) have been invalidated.
_MIGRATION_MARKER = "__migration_monthly_v1"
_MIGRATION_PERIOD = "2026-07"
_MIGRATION_CHANNELS = ("post_coming_soon", "post_major_updates")


class PublicationRepository:
    """Persist publication history to a local SQLite database."""

    def __init__(self, data_dir: str | Path) -> None:
        """Initialize the repository with a directory for the SQLite file."""
        self._db_path = Path(data_dir).resolve() / _DB_FILENAME

    async def init(self) -> None:
        """Create the table if it does not exist."""
        self._db_path.parent.mkdir(parents=True, exist_ok=True, mode=0o777)
        logger.debug(
            "PublicationRepository: db_path=%s parent_exists=%s",
            self._db_path,
            self._db_path.parent.exists(),
        )
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS publication_history (
                    channel_name    TEXT PRIMARY KEY,
                    period          TEXT NOT NULL,
                    message_id      INTEGER,
                    published_at    TEXT NOT NULL
                )
                """,
            )
            await db.commit()

    async def get(self, channel_name: str) -> dict[str, Any] | None:
        """Return the publication record for *channel_name* or ``None``."""
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM publication_history WHERE channel_name = ?",
                (channel_name,),
            )
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def upsert(
        self,
        channel_name: str,
        period: str,
        message_id: int | None,
    ) -> None:
        """Insert or replace the publication record for *channel_name*."""
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                """
                INSERT INTO publication_history (channel_name, period, message_id, published_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(channel_name) DO UPDATE SET
                    period       = excluded.period,
                    message_id   = excluded.message_id,
                    published_at = excluded.published_at
                """,
                (
                    channel_name,
                    period,
                    message_id,
                    datetime.now(UTC).isoformat(),
                ),
            )
            await db.commit()

    async def delete(self, channel_name: str) -> None:
        """Remove the publication record (used by tests to reset)."""
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                "DELETE FROM publication_history WHERE channel_name = ?",
                (channel_name,),
            )
            await db.commit()

    async def run_monthly_migration(self) -> None:
        """One-time invalidation of old July 2026 monthly records.

        The previous ``post_coming_soon`` and ``post_major_updates``
        implementations used placeholder or incorrect logic. This method
        deletes only those two specific records for period ``2026-07``
        so the next ``ChannelScheduler`` run regenerates them with the
        new logic. A marker record prevents re-execution on subsequent
        startups.
        """
        marker = await self.get(_MIGRATION_MARKER)
        if marker is not None:
            return

        for channel_name in _MIGRATION_CHANNELS:
            record = await self.get(channel_name)
            if record is not None and record["period"] == _MIGRATION_PERIOD:
                await self.delete(channel_name)
                logger.info(
                    "Migration: deleted %s record for period %s",
                    channel_name,
                    _MIGRATION_PERIOD,
                )
            else:
                logger.debug(
                    "Migration: no old record for %s — nothing to delete",
                    channel_name,
                )

        await self.upsert(_MIGRATION_MARKER, _MIGRATION_PERIOD, message_id=None)
        logger.info("Migration: monthly v1 complete — will not run again")


# ---------------------------------------------------------------------------
# Channel scheduler
# ---------------------------------------------------------------------------

class ChannelScheduler:
    """Startup-based scheduler for the five poster channels.

    On every ``run()`` call the scheduler checks each registered poster.
    If the current period differs from the stored period the poster is
    executed. In **TEST_MODE** every channel is treated as overdue and runs
    exactly once.
    """

    def __init__(
        self,
        bot: GamingHubBot,
        settings: Settings,
        poster_registry: PosterRegistry,
    ) -> None:
        """Initialize the scheduler with bot, settings, and poster registry."""
        self._bot = bot
        self._settings = settings
        self._registry = poster_registry
        self._repository = PublicationRepository(settings.database_dir)

    async def run(self) -> None:
        """Evaluate every channel and publish when overdue."""
        await self._repository.init()
        is_test = self._settings.test_mode

        if is_test:
            logger.info("TEST_MODE is enabled — will publish every channel once")

        for action, schedule in CHANNEL_SCHEDULES.items():
            poster = self._registry.get(action)
            if poster is None:
                logger.warning("Skipping %s: poster not registered", action)
                continue

            period = current_period(schedule.period_type)
            record = await self._repository.get(action)

            if is_test:
                if record is not None:
                    logger.info(
                        "TEST_MODE: %s already published in this session — skipped",
                        action,
                    )
                    continue
                logger.info(
                    "TEST_MODE: publishing %s (overdue simulation)",
                    action,
                )
                await self._publish(action, poster, period)
                continue

            if record is not None and record["period"] == period:
                logger.info(
                    "%s: already published for period %s — skipped",
                    action,
                    period,
                )
                continue

            logger.info(
                "%s: period %s (stored: %s) — publishing",
                action,
                period,
                record["period"] if record else "(never)",
            )
            await self._publish(action, poster, period)

        logger.info(
            "Channel scheduler run complete (%d channels evaluated)",
            len(CHANNEL_SCHEDULES),
        )

    async def _publish(
        self,
        action: str,
        poster: BasePoster,
        period: str,
    ) -> None:
        """Delete the previous message (if any), publish, record the result."""
        # 1. Delete previous message
        record = await self._repository.get(action)
        if record is not None and record.get("message_id") is not None:
            await self._delete_message(poster.channel_id, record["message_id"])

        # 2. Execute the poster
        result = await poster.execute()

        # 3. Save the result
        message_id = result.message_ids[0] if result.message_ids else None
        await self._repository.upsert(action, period, message_id)

        if result.success:
            logger.info(
                "%s: published %d embed(s), message_id=%s",
                action,
                result.embed_count,
                message_id,
            )
        else:
            logger.warning(
                "%s: publication failed — %s",
                action,
                result.error,
            )

    async def _delete_message(self, channel_id: int, message_id: int) -> None:
        """Try to delete a previously posted message in *channel_id*."""
        try:
            channel = self._bot.get_channel(channel_id) or await self._bot.fetch_channel(channel_id)
            if not isinstance(channel, (discord.TextChannel, discord.Thread)):
                logger.debug("Channel %d is not a text channel — cannot delete message", channel_id)
                return
            msg = await channel.fetch_message(message_id)
            await msg.delete()
            logger.debug("Deleted previous message %d in channel %d", message_id, channel_id)
        except Exception:
            logger.debug(
                "Could not delete message %d in channel %d (may have been deleted already)",
                message_id,
                channel_id,
            )
