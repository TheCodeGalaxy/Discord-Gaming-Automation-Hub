"""Tests for JobScheduler dispatch (calendar only)."""

from __future__ import annotations

import pytest

from gaming_hub.automation.scheduler import JobScheduler


@pytest.mark.unit
class TestJobScheduler:
    """JobScheduler dispatch behavior (calendar-only)."""

    @pytest.mark.asyncio
    async def test_dispatch_unknown_action_raises_value_error(self) -> None:
        """Dispatch to unknown action raises ValueError."""
        scheduler = JobScheduler()
        with pytest.raises(ValueError, match="Unknown action"):
            await scheduler.dispatch("nonexistent", {})

    @pytest.mark.asyncio
    async def test_calendar_sync_returns_error_when_not_configured(self) -> None:
        """Calendar sync returns error when no CalendarService."""
        scheduler = JobScheduler()
        result = await scheduler.dispatch("calendar_sync", {})
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_calendar_reminders_returns_error_when_not_configured(self) -> None:
        """Calendar reminders return error when no CalendarService."""
        scheduler = JobScheduler()
        result = await scheduler.dispatch("calendar_reminders", {})
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_poster_actions_now_raise_unknown(self) -> None:
        """Poster actions are no longer registered in JobScheduler."""
        scheduler = JobScheduler()
        for action in [
            "post_free_this_week",
            "post_crazy_discounts",
            "post_top_this_week",
            "post_major_updates",
            "post_coming_soon",
        ]:
            with pytest.raises(ValueError, match="Unknown action"):
                await scheduler.dispatch(action, {})

    @pytest.mark.asyncio
    async def test_only_calendar_actions_are_registered(self) -> None:
        """Only calendar_sync and calendar_reminders are registered."""
        scheduler = JobScheduler()
        with pytest.raises(ValueError):
            await scheduler.dispatch("post_free_this_week", {})
        # Calendar actions should not raise ValueError (they return results)
        result_sync = await scheduler.dispatch("calendar_sync", {})
        result_remind = await scheduler.dispatch("calendar_reminders", {})
        assert result_sync["success"] is False  # no CalendarService configured
        assert result_remind["success"] is False
