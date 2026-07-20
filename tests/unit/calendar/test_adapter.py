"""Tests for GoogleCalendarAdapter.

Uses mocked HTTP responses — no real Google API calls.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from gaming_hub.calendar.adapter import GoogleCalendarAdapter


def _mock_execute(return_value: object) -> MagicMock:
    """Return a MagicMock whose ``execute()`` returns *return_value* synchronously.

    ``GoogleCalendarAdapter._run`` calls ``request.execute()`` via
    ``run_in_executor`` (i.e. synchronously in a thread), so we must use
    regular ``MagicMock``, not ``AsyncMock``.
    """
    m = MagicMock()
    m.execute.return_value = return_value
    return m


@pytest.fixture
def mock_service() -> MagicMock:
    """Return a mock Google Calendar API service resource."""
    service = MagicMock()
    service.events.return_value = service
    return service


@pytest.fixture
def adapter(mock_service: MagicMock) -> GoogleCalendarAdapter:
    """Return an adapter with a mocked service (bypasses auth)."""
    with patch.object(
        GoogleCalendarAdapter, "_build_service", return_value=mock_service,
    ):
        a = GoogleCalendarAdapter(
            calendar_id="test@calendar.example.com",
            credentials_path=None,
            service_account_json='{"type": "service_account"}',
        )
    return a


@pytest.mark.asyncio
async def test_create_event(adapter: GoogleCalendarAdapter) -> None:
    """Creating an event should return the event ID from Google."""
    request_mock = _mock_execute({"id": "evt_123"})
    adapter._service.events.return_value.insert.return_value = request_mock

    eid = await adapter.create_event(
        title="Test Game", start="2026-08-01", end="2026-08-01",
        reminder_minutes=30,
    )

    assert eid == "evt_123"
    adapter._service.events.return_value.insert.assert_called_once()


@pytest.mark.asyncio
async def test_update_event(adapter: GoogleCalendarAdapter) -> None:
    """Updating an event should call update with correct args."""
    request_mock = _mock_execute({})
    adapter._service.events.return_value.update.return_value = request_mock

    await adapter.update_event(
        "evt_123",
        title="Updated Title",
        start="2026-08-15",
        end="2026-08-15",
        reminder_minutes=60,
        color_id=5,
    )

    adapter._service.events.return_value.update.assert_called_once()
    call_kwargs = adapter._service.events.return_value.update.call_args[1]
    assert call_kwargs["eventId"] == "evt_123"
    assert call_kwargs["body"]["colorId"] == "5"


@pytest.mark.asyncio
async def test_delete_event(adapter: GoogleCalendarAdapter) -> None:
    """Deleting an event should forward the event ID."""
    request_mock = _mock_execute({})
    adapter._service.events.return_value.delete.return_value = request_mock

    await adapter.delete_event("evt_123")

    adapter._service.events.return_value.delete.assert_called_once_with(
        calendarId="test@calendar.example.com", eventId="evt_123",
    )


@pytest.mark.asyncio
async def test_find_events_by_ext_id(adapter: GoogleCalendarAdapter) -> None:
    """Searching by externalId should pass the correct filter."""
    request_mock = _mock_execute({"items": [{"id": "evt_1", "summary": "Found Game"}]})
    adapter._service.events.return_value.list.return_value = request_mock

    results = await adapter.find_events_by_ext_id("coming-soon-123")

    assert len(results) == 1
    assert results[0]["id"] == "evt_1"
    adapter._service.events.return_value.list.assert_called_once()
    call_kwargs = adapter._service.events.return_value.list.call_args[1]
    assert call_kwargs["privateExtendedProperty"] == "externalId=coming-soon-123"


@pytest.mark.asyncio
async def test_list_events_in_range(adapter: GoogleCalendarAdapter) -> None:
    """Listing by range should set timeMin/timeMax correctly."""
    request_mock = _mock_execute({"items": []})
    adapter._service.events.return_value.list.return_value = request_mock

    await adapter.list_events_in_range("2026-01-01", "2026-12-31")

    call_kwargs = adapter._service.events.return_value.list.call_args[1]
    assert call_kwargs["timeMin"] == "2026-01-01T00:00:00Z"
    assert call_kwargs["timeMax"] == "2026-12-31T23:59:59Z"


@pytest.mark.asyncio
async def test_no_reminder_when_zero(adapter: GoogleCalendarAdapter) -> None:
    """When reminder_minutes is 0, no overrides should be set."""
    request_mock = _mock_execute({"id": "evt_no_reminder"})
    adapter._service.events.return_value.insert.return_value = request_mock

    await adapter.create_event(
        title="No Reminder", start="2026-09-01", end="2026-09-01",
        reminder_minutes=0,
    )

    call_kwargs = adapter._service.events.return_value.insert.call_args[1]
    body = call_kwargs["body"]
    assert body["reminders"]["useDefault"] is False
    assert body["reminders"]["overrides"] == []


@pytest.mark.asyncio
async def test_find_events_empty(adapter: GoogleCalendarAdapter) -> None:
    """When no events match, return an empty list."""
    request_mock = _mock_execute({})
    adapter._service.events.return_value.list.return_value = request_mock

    results = await adapter.find_events_by_ext_id("nonexistent")

    assert results == []
