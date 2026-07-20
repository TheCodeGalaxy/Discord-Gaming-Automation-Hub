"""Google Calendar API adapter.

Wraps ``google-api-python-client`` behind the project's ``CalendarAdapter``
port.  Importing this module is safe even when Google dependencies are not
installed — the ``GoogleCalendarAdapter`` class will raise ``ImportError``
at construction time instead.
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from gaming_hub.core.interfaces import CalendarAdapter

if TYPE_CHECKING:
    from googleapiclient.discovery import Resource  # type: ignore[import-untyped]

logger = logging.getLogger(__name__)

# Hard limit: Google Calendar list API caps at 2500 entries per page.
_MAX_RESULTS = 500


class GoogleCalendarAdapter(CalendarAdapter):
    """Concrete adapter for the Google Calendar v3 API.

    Uses a service-account credential file (JSON) supplied by configuration.
    The account must have ``makeChangesToSharedCalendar`` access to the
    target calendar.
    """

    def __init__(
        self,
        calendar_id: str,
        credentials_path: str | None = None,
        service_account_json: str | None = None,
    ) -> None:
        """Build the Google Calendar API service.

        Args:
            calendar_id: Email-address-style calendar ID (e.g. ``"primary"``).
            credentials_path: Path to a service-account JSON file.
            service_account_json: Inline JSON string (takes precedence).

        Raises:
            ImportError: When ``google-api-python-client`` is not installed.
            FileNotFoundError: When *credentials_path* does not exist.
            ValueError: When no credentials source is provided or JSON is invalid.
        """
        self._calendar_id = calendar_id
        self._service = self._build_service(credentials_path, service_account_json)

    @staticmethod
    def _build_service(
        credentials_path: str | None,
        service_account_json: str | None,
    ) -> Resource:
        """Return an authenticated Google Calendar ``Resource``."""
        from google.auth import exceptions as google_auth_exc  # noqa: PLC0415
        from google.oauth2 import service_account  # noqa: PLC0415
        from googleapiclient.discovery import build  # noqa: PLC0415

        scopes = ["https://www.googleapis.com/auth/calendar"]

        try:
            if service_account_json:
                info = json.loads(service_account_json)
                creds = service_account.Credentials.from_service_account_info(  # type: ignore[no-untyped-call]
                    info, scopes=scopes,
                )
            if credentials_path:
                path = Path(credentials_path)
                if not path.exists():
                    raise FileNotFoundError(
                        f"Google service-account file not found: {path}",
                    )
                creds = service_account.Credentials.from_service_account_file(  # type: ignore[no-untyped-call]
                    str(path),
                    scopes=scopes,
                )
            else:
                raise ValueError(
                    "Google Calendar credentials not configured - set "
                    "GOOGLE_SERVICE_ACCOUNT_JSON or GOOGLE_CALENDAR_CREDENTIALS_PATH.",
                )
        except (json.JSONDecodeError, google_auth_exc.GoogleAuthError) as exc:
            raise ValueError(f"Invalid Google Calendar credentials: {exc}") from exc

        return build("calendar", "v3", credentials=creds, cache_discovery=False)

    # ── CalendarAdapter interface ─────────────────────────────────────────

    async def create_event(self, *, title: str, start: str, end: str, reminder_minutes: int) -> str:
        """Create a calendar event and return its Google event ID.

        Args:
            title: Event summary / title.
            start: ISO-8601 date (``YYYY-MM-DD``).
            end: ISO-8601 date (``YYYY-MM-DD``).
            reminder_minutes: Minutes before the event to fire a popup
                notification (``0`` = no reminder).

        Returns:
            The Google Calendar event ID string.
        """
        body = self._build_body(title, start, end, reminder_minutes, color_id=None)
        event = await self._run(
            self._service.events().insert(calendarId=self._calendar_id, body=body),
        )
        eid: str = event.get("id", "")
        return eid

    async def update_event(  # noqa: PLR0913
        self,
        event_id: str,
        *,
        title: str,
        start: str,
        end: str,
        reminder_minutes: int,
        color_id: int | None = None,
    ) -> None:
        """Update an existing calendar event by its Google event ID.

        All fields are overwritten with the provided values.
        """
        body = self._build_body(title, start, end, reminder_minutes, color_id=color_id)
        await self._run(
            self._service.events().update(
                calendarId=self._calendar_id,
                eventId=event_id,
                body=body,
            ),
        )

    async def delete_event(self, event_id: str) -> None:
        """Delete a calendar event by its Google event ID."""
        await self._run(
            self._service.events().delete(
                calendarId=self._calendar_id,
                eventId=event_id,
            ),
        )

    async def find_events_by_ext_id(self, ext_id: str) -> list[dict[str, Any]]:
        """Search for calendar events whose extendedProperties contains *ext_id*.

        Returns a (possibly empty) list of matching event dicts.
        """
        event_list = []
        page_token: str | None = None
        while True:
            resp = await self._run(
                self._service.events().list(
                    calendarId=self._calendar_id,
                    privateExtendedProperty=f"externalId={ext_id}",
                    maxResults=_MAX_RESULTS,
                    pageToken=page_token,
                    singleEvents=True,
                ),
            )
            items: list[dict[str, Any]] = resp.get("items", [])
            event_list.extend(items)
            page_token = resp.get("nextPageToken")
            if not page_token:
                break
        return event_list

    async def list_events_in_range(
        self,
        start_date: str,
        end_date: str,
    ) -> list[dict[str, Any]]:
        """Return all calendar events whose start date falls in *start_date*-*end_date*.

        Both arguments are ISO-8601 dates (``YYYY-MM-DD``).
        """
        event_list = []
        page_token: str | None = None
        while True:
            resp = await self._run(
                self._service.events().list(
                    calendarId=self._calendar_id,
                    timeMin=f"{start_date}T00:00:00Z",
                    timeMax=f"{end_date}T23:59:59Z",
                    maxResults=_MAX_RESULTS,
                    pageToken=page_token,
                    singleEvents=True,
                ),
            )
            items: list[dict[str, Any]] = resp.get("items", [])
            event_list.extend(items)
            page_token = resp.get("nextPageToken")
            if not page_token:
                break
        return event_list

    async def list_all_events(self) -> list[dict[str, Any]]:
        """Return **every** event on the calendar (paginated)."""
        return await self.list_events_in_range("1970-01-01", "2099-12-31")

    # ── Internals ─────────────────────────────────────────────────────────

    @staticmethod
    def _build_body(
        title: str,
        start: str,
        end: str,
        reminder_minutes: int,
        color_id: int | None,
    ) -> dict[str, Any]:
        """Construct the Google Calendar event body dict."""
        body: dict[str, Any] = {
            "summary": title,
            "start": {"date": start, "timeZone": "UTC"},
            "end": {"date": end, "timeZone": "UTC"},
        }
        if color_id is not None:
            body["colorId"] = str(color_id)
        if reminder_minutes > 0:
            body["reminders"] = {
                "useDefault": False,
                "overrides": [
                    {"method": "popup", "minutes": reminder_minutes},
                ],
            }
        else:
            body["reminders"] = {"useDefault": False, "overrides": []}
        return body

    @staticmethod
    async def _run(request: Any) -> Any:
        """Execute a Google API request (thread-safe wrapper).

        ``google-api-python-client`` uses ``httplib2`` (synchronous).
        We offload the call to a thread-pool executor so the async event
        loop is not blocked.
        """
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, request.execute)
