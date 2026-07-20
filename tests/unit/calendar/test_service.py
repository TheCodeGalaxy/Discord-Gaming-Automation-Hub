"""Tests for CalendarService.

All Google API interactions are mocked — no real credentials needed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from gaming_hub.services.calendar_service import CalendarService, SyncReport


# ── Fixtures ────────────────────────────────────────────────────────────────

@dataclass
class FakeGame:
    id: str = "game-1"
    title: str = "Test Game"
    release_date: date | None = date(2026, 8, 15)
    description: str | None = "A test game"
    genres: list[str] = field(default_factory=lambda: ["Action"])
    platforms: list[str] = field(default_factory=lambda: ["PC"])
    developers: list[str] = field(default_factory=lambda: ["DevCo"])
    publishers: list[str] = field(default_factory=lambda: ["PubCo"])
    steam_app_id: int | None = 12345
    epic_namespace: str | None = None
    cover_url: Any = None
    provider_name: str = "rawg"
    metacritic_score: int | None = 85
    steam_review_score: float | None = 92.0


@dataclass
class FakeGameUpdate:
    app_id: int = 12345
    title: str = "patch-1"
    game_name: str = "Test Game"
    update_title: str = "Major Patch v2.0"
    url: str = "https://store.steampowered.com/news/app/12345"
    date: datetime = field(default_factory=lambda: datetime(2026, 8, 20, tzinfo=UTC))
    snippet: str = "Fixed all the bugs"
    score: int = 50


@dataclass
class FakeNewReleasesResult:
    games: list[Any] = field(default_factory=list)
    total: int = 0
    errors: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class FakeMajorUpdatesResult:
    updates: list[Any] = field(default_factory=list)
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
def mock_new_releases() -> MagicMock:
    m = MagicMock()
    m.get_year_releases = AsyncMock(
        return_value=FakeNewReleasesResult(games=[FakeGame()]),
    )
    return m


@pytest.fixture
def mock_major_updates() -> MagicMock:
    m = MagicMock()
    m.get_major_updates = AsyncMock(
        return_value=FakeMajorUpdatesResult(updates=[]),
    )
    return m


@pytest.fixture
def settings() -> MagicMock:
    s = MagicMock()
    s.enable_google_calendar = True
    s.google_calendar_id = "test@calendar.com"
    s.google_sync_years_ahead = 1
    s.google_sync_on_startup = False
    s.google_delete_old_events = False
    s.google_calendar_default_reminder_minutes = 60
    s.google_event_color_releases = 9
    s.google_event_color_updates = 10
    return s


@pytest.fixture
def service(
    settings: MagicMock,
    mock_adapter: MagicMock,
    mock_new_releases: MagicMock,
    mock_major_updates: MagicMock,
) -> CalendarService:
    return CalendarService(
        settings,
        new_releases_service=mock_new_releases,
        major_updates_service=mock_major_updates,
        adapter=mock_adapter,
    )


# ── Tests ───────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_sync_creates_and_tags_events(service: CalendarService) -> None:
    """A full sync should create events for games and updates."""
    report = await service.sync()

    assert report.created >= 1
    assert report.updated == 0
    assert len(report.errors) == 0


@pytest.mark.asyncio
async def test_sync_updates_existing_events(service: CalendarService, mock_adapter: MagicMock) -> None:
    """When an event already exists, update it instead of creating."""
    mock_adapter.find_events_by_ext_id = AsyncMock(
        return_value=[{"id": "existing_evt"}],
    )

    report = await service.sync()

    assert report.updated >= 1
    assert report.created == 0


@pytest.mark.asyncio
async def test_sync_no_adapter(settings: MagicMock) -> None:
    """When no adapter is set, sync should report an error."""
    svc = CalendarService(settings)
    report = await svc.sync()

    assert len(report.errors) > 0
    assert "Google Calendar not configured" in report.errors[0]


@pytest.mark.asyncio
async def test_sync_year_only(service: CalendarService) -> None:
    """sync_year only syncs the specified year's games."""
    report = await service.sync_year(2026)

    assert report.created >= 1
    assert report.finished_at is not None


@pytest.mark.asyncio
async def test_delete_past_events(service: CalendarService, mock_adapter: MagicMock) -> None:
    """Deleting past events should call delete for each event."""
    mock_adapter.list_events_in_range = AsyncMock(
        return_value=[{"id": "old_evt_1"}, {"id": "old_evt_2"}],
    )

    deleted = await service.delete_past_events()

    assert deleted == 2
    assert mock_adapter.delete_event.await_count == 2


@pytest.mark.asyncio
async def test_delete_past_events_no_adapter(settings: MagicMock) -> None:
    """Without an adapter, delete_past_events returns 0."""
    svc = CalendarService(settings)
    deleted = await svc.delete_past_events()

    assert deleted == 0


@pytest.mark.asyncio
async def test_create_event_exposed(service: CalendarService) -> None:
    """The public create_event method delegates to the adapter."""
    eid = await service.create_event(
        title="Manual Event", start="2026-09-01", end="2026-09-01",
    )
    assert eid == "evt_created"


@pytest.mark.asyncio
async def test_create_event_no_adapter(settings: MagicMock) -> None:
    """Without an adapter, create_event returns None."""
    svc = CalendarService(settings)
    eid = await svc.create_event(title="Test", start="2026-09-01", end="2026-09-01")
    assert eid is None


@pytest.mark.asyncio
async def test_find_events_by_ext_id_exposed(service: CalendarService, mock_adapter: MagicMock) -> None:
    """The public find_events_by_ext_id method delegates to the adapter."""
    mock_adapter.find_events_by_ext_id = AsyncMock(return_value=[{"id": "found"}])
    results = await service.find_events_by_ext_id("coming-soon-123")
    assert len(results) == 1
    assert results[0]["id"] == "found"


@pytest.mark.asyncio
async def test_game_without_release_date_skipped(service: CalendarService, mock_new_releases: MagicMock) -> None:
    """Games without a release date should not create calendar events."""
    mock_new_releases.get_year_releases = AsyncMock(
        return_value=FakeNewReleasesResult(games=[FakeGame(release_date=None)]),
    )
    report = await service.sync()
    # 26 seasonal events (13 per year × 2 years)
    assert report.created == 26


@pytest.mark.asyncio
async def test_sync_handles_api_failure_gracefully(service: CalendarService, mock_adapter: MagicMock) -> None:
    """API failures should be logged and not crash the service."""
    mock_adapter.create_event = AsyncMock(side_effect=Exception("API error"))

    report = await service.sync()

    assert len(report.errors) >= 1
    # With game + seasonal for 2 years, all 27 events fail
    assert report.created == 0


@pytest.mark.asyncio
async def test_sync_report_elapsed(service: CalendarService) -> None:
    """SyncReport.elapsed_seconds should be positive after completion."""
    report = await service.sync()
    assert report.elapsed_seconds > 0


@pytest.mark.asyncio
async def test_sync_sale_events_legacy(service: CalendarService) -> None:
    """Legacy sync_sale_events returns 0."""
    result = await service.sync_sale_events()
    assert result == 0


@pytest.mark.asyncio
async def test_check_reminders_legacy(service: CalendarService) -> None:
    """Legacy check_reminders returns empty list."""
    result = await service.check_reminders()
    assert result == []


@pytest.mark.asyncio
async def test_send_reminders_legacy(service: CalendarService) -> None:
    """Legacy send_reminders returns 0."""
    now = datetime.now(UTC)
    result = await service.send_reminders(now, now)
    assert result == 0


@pytest.mark.asyncio
async def test_sync_with_major_updates(settings: MagicMock, mock_adapter: MagicMock, mock_new_releases: MagicMock) -> None:
    """When major updates service returns updates, events should be created."""
    updates_svc = MagicMock()
    updates_svc.get_major_updates = AsyncMock(
        return_value=FakeMajorUpdatesResult(updates=[FakeGameUpdate()]),
    )
    upsert_settings = settings
    upsert_settings.google_sync_years_ahead = 0

    svc = CalendarService(
        upsert_settings,
        new_releases_service=mock_new_releases,
        major_updates_service=updates_svc,
        adapter=mock_adapter,
    )

    report = await svc.sync()

    # 1 game + 13 seasonal + 1 update = 15 events
    assert report.created == 15
    assert report.updated == 0
    assert len(report.errors) == 0
