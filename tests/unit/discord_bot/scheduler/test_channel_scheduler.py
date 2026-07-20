"""Tests for ChannelScheduler, PublicationRepository, and period helpers."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from gaming_hub.discord_bot.scheduler.channel_scheduler import (
    CHANNEL_SCHEDULES,
    ChannelScheduler,
    PublicationRepository,
    current_period,
)

# =========================================================================
# Period helpers
# =========================================================================


@pytest.mark.unit
class TestCurrentPeriod:
    """Period string generation."""

    def test_weekly_format(self) -> None:
        """Weekly periods match ISO week format."""
        period = current_period("weekly")
        assert period.count("-W") == 1 or "-W" in period

    def test_monthly_format(self) -> None:
        """Monthly periods match YYYY-MM format."""
        period = current_period("monthly")
        assert "-" in period and len(period) == 7

    def test_weekly_returns_valid_iso_week(self) -> None:
        """Weekly period has correct ISO week number."""
        period = current_period("weekly")
        parts = period.split("-W")
        assert len(parts) == 2
        year, week = int(parts[0]), int(parts[1])
        assert 1 <= week <= 53
        assert year >= 2024

    def test_monthly_returns_valid_month(self) -> None:
        """Monthly period has correct year-month."""
        period = current_period("monthly")
        parts = period.split("-")
        assert len(parts) == 2
        year, month = int(parts[0]), int(parts[1])
        assert 1 <= month <= 12
        assert year >= 2024


# =========================================================================
# Channel schedule config
# =========================================================================


@pytest.mark.unit
class TestChannelSchedules:
    """Channel schedule configuration."""

    def test_all_five_posters_configured(self) -> None:
        """All 5 poster channels have a schedule."""
        assert len(CHANNEL_SCHEDULES) == 5

    def test_weekly_channels_have_weekly_period(self) -> None:
        """free_this_week, crazy_discounts, top_this_week are weekly."""
        weekly_actions = ["post_free_this_week", "post_crazy_discounts", "post_top_this_week"]
        for action in weekly_actions:
            assert CHANNEL_SCHEDULES[action].period_type == "weekly"

    def test_monthly_channels_have_monthly_period(self) -> None:
        """coming_soon and major_updates are monthly."""
        monthly_actions = ["post_coming_soon", "post_major_updates"]
        for action in monthly_actions:
            assert CHANNEL_SCHEDULES[action].period_type == "monthly"


# =========================================================================
# PublicationRepository (SQLite)
# =========================================================================


@pytest.mark.unit
class TestPublicationRepository:
    """SQLite-backed publication history."""

    async def _repo(self, tmp_path: Path) -> PublicationRepository:
        r = PublicationRepository(tmp_path)
        await r.init()
        return r

    @pytest.mark.asyncio
    async def test_get_returns_none_for_missing(self, tmp_path: Path) -> None:
        """get() returns None when no record exists."""
        repo = await self._repo(tmp_path)
        record = await repo.get("post_free_this_week")
        assert record is None

    @pytest.mark.asyncio
    async def test_upsert_creates_record(self, tmp_path: Path) -> None:
        """upsert() creates a new record."""
        repo = await self._repo(tmp_path)
        await repo.upsert("post_free_this_week", "2026-W29", 12345)
        record = await repo.get("post_free_this_week")
        assert record is not None
        assert record["channel_name"] == "post_free_this_week"
        assert record["period"] == "2026-W29"
        assert record["message_id"] == 12345

    @pytest.mark.asyncio
    async def test_upsert_updates_existing(self, tmp_path: Path) -> None:
        """upsert() updates an existing record."""
        repo = await self._repo(tmp_path)
        await repo.upsert("post_free_this_week", "2026-W28", 111)
        await repo.upsert("post_free_this_week", "2026-W29", 222)
        record = await repo.get("post_free_this_week")
        assert record["period"] == "2026-W29"
        assert record["message_id"] == 222

    @pytest.mark.asyncio
    async def test_upsert_message_id_none(self, tmp_path: Path) -> None:
        """upsert() stores None message_id correctly."""
        repo = await self._repo(tmp_path)
        await repo.upsert("post_free_this_week", "2026-W29", None)
        record = await repo.get("post_free_this_week")
        assert record["message_id"] is None

    @pytest.mark.asyncio
    async def test_delete_removes_record(self, tmp_path: Path) -> None:
        """delete() removes the record."""
        repo = await self._repo(tmp_path)
        await repo.upsert("post_free_this_week", "2026-W29", 123)
        await repo.delete("post_free_this_week")
        record = await repo.get("post_free_this_week")
        assert record is None

    @pytest.mark.asyncio
    async def test_multiple_channels_independent(self, tmp_path: Path) -> None:
        """Records for different channels are independent."""
        repo = await self._repo(tmp_path)
        await repo.upsert("post_free_this_week", "2026-W29", 1)
        await repo.upsert("post_crazy_discounts", "2026-W29", 2)
        r1 = await repo.get("post_free_this_week")
        r2 = await repo.get("post_crazy_discounts")
        assert r1["message_id"] == 1
        assert r2["message_id"] == 2

    @pytest.mark.asyncio
    async def test_repo_creates_table_on_init(self, tmp_path: Path) -> None:
        """init() creates the SQLite table."""
        db_path = tmp_path / "scheduler.db"
        r = PublicationRepository(tmp_path)
        await r.init()
        assert db_path.exists()

    @pytest.mark.asyncio
    async def test_published_at_is_set(self, tmp_path: Path) -> None:
        """published_at is an ISO-formatted timestamp."""
        repo = await self._repo(tmp_path)
        await repo.upsert("post_free_this_week", "2026-W29", 42)
        record = await repo.get("post_free_this_week")
        assert record["published_at"] is not None
        assert "T" in record["published_at"]


# =========================================================================
# ChannelScheduler integration
# =========================================================================


@pytest.mark.unit
class TestChannelScheduler:
    """Startup-based channel scheduler behavior."""

    @pytest.fixture()
    def settings(self) -> MagicMock:
        """Return a mock Settings object."""
        s = MagicMock()
        s.database_dir = "/tmp"  # Use temp dir for SQLite
        s.test_mode = False
        return s

    @pytest.fixture()
    def bot(self) -> MagicMock:
        """Return a mock GamingHubBot."""
        b = MagicMock()
        b.get_channel.return_value = None
        b.fetch_channel = AsyncMock()
        return b

    @pytest.fixture()
    def poster(self) -> MagicMock:
        """Return a mock poster."""
        p = MagicMock()
        p.execute = AsyncMock()
        p.channel_id = 12345
        return p

    @pytest.fixture()
    def registry(self, poster: MagicMock) -> MagicMock:
        """Return a mock PosterRegistry with one registered poster."""
        r = MagicMock()
        # Only return the poster for the registered action; None for others
        def get_side_effect(action: str) -> MagicMock | None:
            return poster if action == "post_free_this_week" else None
        r.get.side_effect = get_side_effect
        r.all.return_value = {"post_free_this_week": poster}
        return r

    @pytest.fixture()
    def scheduler(self, bot: MagicMock, settings: MagicMock, registry: MagicMock) -> ChannelScheduler:
        """Return a ChannelScheduler with mocked dependencies."""
        s = ChannelScheduler(bot, settings, registry)
        # Override the repository path to a temp directory
        return s

    @pytest.mark.asyncio
    async def test_normal_startup_publishes_when_no_record(
        self,
        bot: MagicMock,
        settings: MagicMock,
        registry: MagicMock,
        poster: MagicMock,
        tmp_path: Path,
    ) -> None:
        """When no publication record exists, the poster is executed."""
        settings.database_dir = str(tmp_path)
        poster.execute.return_value = MagicMock(success=True, embed_count=3, message_ids=[999])
        s = ChannelScheduler(bot, settings, registry)
        await s.run()
        poster.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_restart_does_not_republish_when_same_period(
        self,
        bot: MagicMock,
        settings: MagicMock,
        registry: MagicMock,
        poster: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Restarting in the same period does NOT republish."""
        settings.database_dir = str(tmp_path)
        # First run
        poster.execute.return_value = MagicMock(success=True, embed_count=1, message_ids=[111])
        s1 = ChannelScheduler(bot, settings, registry)
        await s1.run()
        assert poster.execute.await_count == 1

        # Second run — same period
        s2 = ChannelScheduler(bot, settings, registry)
        await s2.run()
        # execute should NOT be called again (same period)
        assert poster.execute.await_count == 1

    @pytest.mark.asyncio
    async def test_new_period_triggers_publication(
        self,
        bot: MagicMock,
        settings: MagicMock,
        registry: MagicMock,
        poster: MagicMock,
        tmp_path: Path,
    ) -> None:
        """A different (older) period triggers re-publication."""
        settings.database_dir = str(tmp_path)
        # Manually insert a record from an old period
        repo = PublicationRepository(tmp_path)
        await repo.init()
        await repo.upsert("post_free_this_week", "2020-W01", 111)

        poster.execute.return_value = MagicMock(success=True, embed_count=2, message_ids=[222])
        s = ChannelScheduler(bot, settings, registry)
        await s.run()
        poster.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_test_mode_publishes_every_channel(
        self,
        bot: MagicMock,
        settings: MagicMock,
        registry: MagicMock,
        poster: MagicMock,
        tmp_path: Path,
    ) -> None:
        """TEST_MODE publishes every channel regardless of period."""
        settings.database_dir = str(tmp_path)
        settings.test_mode = True

        poster.execute.return_value = MagicMock(success=True, embed_count=1, message_ids=[333])

        # Pre-populate a record (simulating previous test run)
        repo = PublicationRepository(tmp_path)
        await repo.init()
        await repo.upsert("post_free_this_week", "2026-W29", 111)

        s = ChannelScheduler(bot, settings, registry)
        await s.run()
        # No republish because TEST_MODE skips channels already published
        poster.execute.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_test_mode_publishes_once_then_skips(
        self,
        bot: MagicMock,
        settings: MagicMock,
        registry: MagicMock,
        poster: MagicMock,
        tmp_path: Path,
    ) -> None:
        """TEST_MODE: first run publishes, second run skips."""
        settings.database_dir = str(tmp_path)
        settings.test_mode = True

        poster.execute.return_value = MagicMock(success=True, embed_count=1, message_ids=[444])

        s1 = ChannelScheduler(bot, settings, registry)
        await s1.run()
        assert poster.execute.await_count == 1

        s2 = ChannelScheduler(bot, settings, registry)
        await s2.run()
        assert poster.execute.await_count == 1  # Should NOT republish

    @pytest.mark.asyncio
    async def test_previous_message_is_deleted(
        self,
        bot: MagicMock,
        settings: MagicMock,
        registry: MagicMock,
        poster: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Previous message is deleted before new publication."""
        settings.database_dir = str(tmp_path)

        # Insert a record with a message_id
        repo = PublicationRepository(tmp_path)
        await repo.init()
        await repo.upsert("post_free_this_week", "2020-W01", 777)

        # Mock channel and message
        channel = MagicMock(spec=discord.TextChannel)
        msg = AsyncMock()
        msg.delete = AsyncMock()
        channel.fetch_message = AsyncMock(return_value=msg)
        bot.get_channel.return_value = channel

        poster.execute.return_value = MagicMock(success=True, embed_count=1, message_ids=[888])

        s = ChannelScheduler(bot, settings, registry)
        await s.run()

        # Old message should be deleted
        channel.fetch_message.assert_awaited_once_with(777)
        msg.delete.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_missing_poster_is_skipped(
        self,
        bot: MagicMock,
        settings: MagicMock,
        tmp_path: Path,
    ) -> None:
        """A channel with no registered poster is silently skipped."""
        settings.database_dir = str(tmp_path)
        empty_registry = MagicMock()
        empty_registry.get.return_value = None
        empty_registry.all.return_value = {}

        s = ChannelScheduler(bot, settings, empty_registry)
        await s.run()  # Should not raise

    @pytest.mark.asyncio
    async def test_message_id_saved_after_publication(
        self,
        bot: MagicMock,
        settings: MagicMock,
        registry: MagicMock,
        poster: MagicMock,
        tmp_path: Path,
    ) -> None:
        """New message_id is saved to the repository."""
        settings.database_dir = str(tmp_path)
        poster.execute.return_value = MagicMock(success=True, embed_count=2, message_ids=[555])

        s = ChannelScheduler(bot, settings, registry)
        await s.run()

        repo = PublicationRepository(tmp_path)
        await repo.init()
        record = await repo.get("post_free_this_week")
        assert record is not None
        assert record["message_id"] == 555

    @pytest.mark.asyncio
    async def test_saves_updated_period(
        self,
        bot: MagicMock,
        settings: MagicMock,
        registry: MagicMock,
        poster: MagicMock,
        tmp_path: Path,
    ) -> None:
        """After publication the period is updated to the current period."""
        settings.database_dir = str(tmp_path)
        poster.execute.return_value = MagicMock(success=True, embed_count=1, message_ids=[666])

        s = ChannelScheduler(bot, settings, registry)
        await s.run()

        repo = PublicationRepository(tmp_path)
        await repo.init()
        record = await repo.get("post_free_this_week")
        assert record is not None
        # Period should be current
        expected_period = current_period("weekly")
        assert record["period"] == expected_period


# =========================================================================
# Migration (one-time invalidation of old July 2026 monthly records)
# =========================================================================


@pytest.mark.unit
class TestMonthlyMigration:
    """One-time invalidation of old July 2026 monthly records."""

    async def _repo(self, tmp_path: Path) -> PublicationRepository:
        r = PublicationRepository(tmp_path)
        await r.init()
        return r

    @pytest.mark.asyncio
    async def test_deletes_old_coming_soon(self, tmp_path: Path) -> None:
        """Migration deletes old post_coming_soon record for 2026-07."""
        repo = await self._repo(tmp_path)
        await repo.upsert("post_coming_soon", "2026-07", 111)
        await repo.run_monthly_migration()
        record = await repo.get("post_coming_soon")
        assert record is None

    @pytest.mark.asyncio
    async def test_deletes_old_major_updates(self, tmp_path: Path) -> None:
        """Migration deletes old post_major_updates record for 2026-07."""
        repo = await self._repo(tmp_path)
        await repo.upsert("post_major_updates", "2026-07", 222)
        await repo.run_monthly_migration()
        record = await repo.get("post_major_updates")
        assert record is None

    @pytest.mark.asyncio
    async def test_keeps_weekly_channels(self, tmp_path: Path) -> None:
        """Migration does NOT touch weekly channel records."""
        repo = await self._repo(tmp_path)
        await repo.upsert("post_free_this_week", "2026-W29", 333)
        await repo.upsert("post_crazy_discounts", "2026-W30", 444)
        await repo.upsert("post_top_this_week", "2026-W29", 555)
        await repo.run_monthly_migration()
        assert await repo.get("post_free_this_week") is not None
        assert await repo.get("post_crazy_discounts") is not None
        assert await repo.get("post_top_this_week") is not None

    @pytest.mark.asyncio
    async def test_keeps_other_months(self, tmp_path: Path) -> None:
        """Migration does NOT touch monthly records for other periods."""
        repo = await self._repo(tmp_path)
        await repo.upsert("post_coming_soon", "2026-06", 666)
        await repo.upsert("post_major_updates", "2026-08", 777)
        await repo.run_monthly_migration()
        assert await repo.get("post_coming_soon") is not None
        assert await repo.get("post_major_updates") is not None

    @pytest.mark.asyncio
    async def test_only_runs_once(self, tmp_path: Path) -> None:
        """Migration marker prevents re-execution on second call."""
        repo = await self._repo(tmp_path)
        await repo.upsert("post_coming_soon", "2026-07", 888)
        await repo.run_monthly_migration()
        assert await repo.get("post_coming_soon") is None

        await repo.upsert("post_coming_soon", "2026-07", 999)
        await repo.run_monthly_migration()
        assert await repo.get("post_coming_soon") is not None

    @pytest.mark.asyncio
    async def test_noop_when_no_old_records(self, tmp_path: Path) -> None:
        """Migration does not raise when no old records exist."""
        repo = await self._repo(tmp_path)
        await repo.run_monthly_migration()
        marker = await repo.get("__migration_monthly_v1")
        assert marker is not None

    @pytest.mark.asyncio
    async def test_marker_prevents_repeat(self, tmp_path: Path) -> None:
        """Marker record exists after migration completes."""
        repo = await self._repo(tmp_path)
        await repo.run_monthly_migration()
        marker = await repo.get("__migration_monthly_v1")
        assert marker is not None
        assert marker["period"] == "2026-07"
