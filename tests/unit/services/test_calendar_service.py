"""Unit tests for CalendarService."""
# ruff: noqa: PLR2004 — test assertions use literal magic values

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from gaming_hub.services.calendar_service import CalendarService


@pytest.fixture()
def settings() -> MagicMock:
    """Return mock settings with Google Calendar disabled by default."""
    s = MagicMock()
    s.enable_google_calendar = False
    s.google_calendar_id = "primary"
    s.google_sync_years_ahead = 1
    s.google_sync_on_startup = False
    s.google_delete_old_events = False
    s.google_calendar_default_reminder_minutes = 60
    s.google_event_color_releases = 9
    s.google_event_color_updates = 10
    return s


# ── Graceful degradation when Google Calendar is not configured ──────────


@pytest.mark.unit
class TestCalendarServiceDegradation:
    """All methods should work without a configured adapter."""

    def test_no_adapter_does_not_raise(self, settings: MagicMock) -> None:
        """Constructing CalendarService without credentials should NOT raise."""
        svc = CalendarService(settings)
        assert svc._adapter is None

    @pytest.mark.asyncio
    async def test_sync_returns_report_with_errors(self, settings: MagicMock) -> None:
        """sync() returns a report with an error message when no adapter."""
        svc = CalendarService(settings)
        report = await svc.sync()
        assert len(report.errors) > 0

    @pytest.mark.asyncio
    async def test_sync_year_returns_empty_report(self, settings: MagicMock) -> None:
        """sync_year() returns a zeroed report when no adapter."""
        svc = CalendarService(settings)
        report = await svc.sync_year(2026)
        assert report.created == 0

    @pytest.mark.asyncio
    async def test_create_event_returns_none(self, settings: MagicMock) -> None:
        """create_event() returns None when no adapter."""
        svc = CalendarService(settings)
        eid = await svc.create_event(title="Test", start="2026-08-01", end="2026-08-01")
        assert eid is None

    @pytest.mark.asyncio
    async def test_update_event_returns_false(self, settings: MagicMock) -> None:
        """update_event() returns False when no adapter."""
        svc = CalendarService(settings)
        ok = await svc.update_event("evt_1", title="Test", start="2026-08-01", end="2026-08-01")
        assert ok is False

    @pytest.mark.asyncio
    async def test_delete_event_returns_false(self, settings: MagicMock) -> None:
        """delete_event() returns False when no adapter."""
        svc = CalendarService(settings)
        ok = await svc.delete_event("evt_1")
        assert ok is False

    @pytest.mark.asyncio
    async def test_delete_past_events_returns_zero(self, settings: MagicMock) -> None:
        """delete_past_events() returns 0 when no adapter."""
        svc = CalendarService(settings)
        deleted = await svc.delete_past_events()
        assert deleted == 0

    @pytest.mark.asyncio
    async def test_find_events_returns_empty(self, settings: MagicMock) -> None:
        """find_events_by_ext_id() returns [] when no adapter."""
        svc = CalendarService(settings)
        results = await svc.find_events_by_ext_id("test-id")
        assert results == []


# ── Legacy stubs ─────────────────────────────────────────────────────────


@pytest.mark.unit
class TestCalendarServiceLegacy:
    """Backward-compatible stub methods."""

    def setup_method(self) -> None:
        self.svc = CalendarService(MagicMock())

    @pytest.mark.asyncio
    async def test_sync_sale_events_returns_zero(self) -> None:
        result = await self.svc.sync_sale_events()
        assert result == 0

    @pytest.mark.asyncio
    async def test_check_reminders_returns_empty(self) -> None:
        result = await self.svc.check_reminders()
        assert result == []

    @pytest.mark.asyncio
    async def test_send_reminders_returns_zero(self) -> None:
        now = datetime.now(UTC)
        result = await self.svc.send_reminders(now, now)
        assert result == 0


# ── Full sync orchestration ──────────────────────────────────────────────


@dataclass
class _FakeGame:
    id: str = "game-1"
    title: str = "Test Game"
    release_date: date | None = None
    description: str | None = None
    genres: list[str] = field(default_factory=list)
    platforms: list[str] = field(default_factory=list)
    developers: list[str] = field(default_factory=list)
    publishers: list[str] = field(default_factory=list)
    steam_app_id: int | None = 12345
    epic_namespace: str | None = None
    cover_url: Any = None
    provider_name: str = "rawg"
    metacritic_score: int | None = None
    steam_review_score: float | None = None


@dataclass
class _FakeUpdate:
    app_id: int = 12345
    title: str = "patch-1"
    game_name: str = "Test Game"
    update_title: str = "Major Patch"
    url: str = "https://example.com"
    date: datetime = field(default_factory=lambda: datetime(2026, 8, 20, tzinfo=UTC))
    snippet: str = "Patch notes"
    score: int = 50


@dataclass
class _FakeResult:
    games: list[Any] = field(default_factory=list)
    total: int = 0
    errors: list[dict[str, Any]] = field(default_factory=list)


@pytest.fixture
def mock_adapter() -> MagicMock:
    a = MagicMock()
    a.create_event = AsyncMock(return_value="evt_created")
    a.update_event = AsyncMock(return_value=None)
    a.delete_event = AsyncMock(return_value=None)
    a.find_events_by_ext_id = AsyncMock(return_value=[])
    a.list_events_in_range = AsyncMock(return_value=[])
    a._service = MagicMock()
    a._calendar_id = "test@calendar.com"
    a._run = AsyncMock(return_value=None)
    return a


@pytest.fixture
def enabled_settings() -> MagicMock:
    s = MagicMock()
    s.enable_google_calendar = True
    s.google_calendar_id = "test@calendar.com"
    s.google_sync_years_ahead = 0
    s.google_sync_on_startup = False
    s.google_delete_old_events = False
    s.google_calendar_default_reminder_minutes = 60
    s.google_event_color_releases = 9
    s.google_event_color_updates = 10
    return s


@pytest.mark.unit
class TestCalendarServiceSync:
    """Synchronisation of game release events."""

    @pytest.mark.asyncio
    async def test_sync_creates_events_for_releases(
        self,
        enabled_settings: MagicMock,
        mock_adapter: MagicMock,
    ) -> None:
        """sync() creates calendar events for games with release dates."""
        game = _FakeGame(release_date=date(2026, 8, 15))
        new_svc = MagicMock()
        new_svc.get_year_releases = AsyncMock(return_value=_FakeResult(games=[game]))

        svc = CalendarService(
            enabled_settings,
            new_releases_service=new_svc,
            adapter=mock_adapter,
        )
        report = await svc.sync()
        # 1 game + 13 seasonal events
        assert report.created == 14

    @pytest.mark.asyncio
    async def test_sync_updates_existing_events(
        self,
        enabled_settings: MagicMock,
        mock_adapter: MagicMock,
    ) -> None:
        """When an event already exists, update it instead of creating."""
        mock_adapter.find_events_by_ext_id = AsyncMock(
            return_value=[{"id": "existing_evt"}],
        )
        game = _FakeGame(release_date=date(2026, 8, 15))
        new_svc = MagicMock()
        new_svc.get_year_releases = AsyncMock(return_value=_FakeResult(games=[game]))

        svc = CalendarService(
            enabled_settings,
            new_releases_service=new_svc,
            adapter=mock_adapter,
        )
        report = await svc.sync()
        # 1 game + 13 seasonal events — all found as existing
        assert report.updated == 14
        assert report.created == 0

    @pytest.mark.asyncio
    async def test_sync_skips_game_without_release_date(
        self,
        enabled_settings: MagicMock,
        mock_adapter: MagicMock,
    ) -> None:
        """Games without a release date should NOT create events."""
        game = _FakeGame(release_date=None)
        new_svc = MagicMock()
        new_svc.get_year_releases = AsyncMock(return_value=_FakeResult(games=[game]))

        svc = CalendarService(
            enabled_settings,
            new_releases_service=new_svc,
            adapter=mock_adapter,
        )
        report = await svc.sync()
        # 13 seasonal events created (game has no release date, so skipped)
        assert report.created == 13

    @pytest.mark.asyncio
    async def test_sync_api_failure_does_not_crash(
        self,
        enabled_settings: MagicMock,
        mock_adapter: MagicMock,
    ) -> None:
        """Google API failures are logged and do not crash the service."""
        mock_adapter.create_event = AsyncMock(side_effect=Exception("API error"))
        game = _FakeGame(release_date=date(2026, 8, 15))
        new_svc = MagicMock()
        new_svc.get_year_releases = AsyncMock(return_value=_FakeResult(games=[game]))

        svc = CalendarService(
            enabled_settings,
            new_releases_service=new_svc,
            adapter=mock_adapter,
        )
        report = await svc.sync()
        assert len(report.errors) >= 1

    @pytest.mark.asyncio
    async def test_delete_past_events(
        self,
        enabled_settings: MagicMock,
        mock_adapter: MagicMock,
    ) -> None:
        """delete_past_events removes old events and returns the count."""
        mock_adapter.list_events_in_range = AsyncMock(
            return_value=[{"id": "old_1"}, {"id": "old_2"}],
        )
        svc = CalendarService(
            enabled_settings,
            adapter=mock_adapter,
        )
        deleted = await svc.delete_past_events()
        assert deleted == 2
