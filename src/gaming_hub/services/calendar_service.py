"""Calendar service — Google Calendar integration for releases and updates.

This is the HIGH-LEVEL orchestrator that consumes NewReleasesService and
MajorUpdatesService to mirror project data as Google Calendar events.

The low-level Google Calendar API wrapper lives in ``calendar/adapter.py``.

Everything is optional — when ``enable_google_calendar`` is ``False`` the
service degrades gracefully with no API calls.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import TYPE_CHECKING, Any

from gaming_hub.calendar.events import seasonal_events_for_year

if TYPE_CHECKING:
    from gaming_hub.calendar.adapter import GoogleCalendarAdapter
    from gaming_hub.config.models import Settings
    from gaming_hub.services.major_updates_service import MajorUpdatesService
    from gaming_hub.services.new_releases_service import NewReleasesService

logger = logging.getLogger(__name__)

_EXT_ID_KEY = "externalId"
_EXT_SOURCE_KEY = "source"
_PREFIX_COMING_SOON = "coming-soon"
_PREFIX_UPDATE = "update"


@dataclass
class SyncReport:
    """Summary of one calendar-sync run."""

    created: int = 0
    updated: int = 0
    deleted: int = 0
    errors: list[str] = field(default_factory=list)
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    finished_at: datetime | None = None

    @property
    def elapsed_seconds(self) -> float:
        """Return the number of seconds elapsed since the sync started."""
        end = self.finished_at or datetime.now(UTC)
        return (end - self.started_at).total_seconds()


class CalendarService:
    """Bridge between provider release/update data and Google Calendar.

    All Google API errors are caught and logged — they never propagate
    to the caller.
    """

    def __init__(
        self,
        settings: Settings,
        new_releases_service: NewReleasesService | None = None,
        major_updates_service: MajorUpdatesService | None = None,
        adapter: GoogleCalendarAdapter | None = None,
    ) -> None:
        """Store dependencies — all are optional for graceful degradation."""
        self._settings = settings
        self._new_releases = new_releases_service
        self._major_updates = major_updates_service
        self._adapter = adapter

    # ------------------------------------------------------------------
    # Full sync
    # ------------------------------------------------------------------

    async def sync(self) -> SyncReport:
        """Perform a full synchronisation of all data to Google Calendar.

        Requires a configured adapter and services.  If any are missing the
        report will contain error messages but no exception will be raised.
        """
        report = SyncReport()
        logger.info("Calendar Sync Started")

        if not self._adapter:
            report.errors.append("Google Calendar not configured")
            report.finished_at = datetime.now(UTC)
            return report

        years_ahead = self._settings.google_sync_years_ahead
        today = date.today()
        start_year = today.year
        end_year = today.year + years_ahead

        for year in range(start_year, end_year + 1):
            await self._sync_year_games(year, report)
            await self._sync_seasonal_events(year, report)

        await self._sync_updates(report)

        if self._settings.google_delete_old_events:
            deleted = await self.delete_past_events()
            report.deleted = deleted

        report.finished_at = datetime.now(UTC)
        logger.info(
            "Calendar Sync Finished — created=%d updated=%d deleted=%d errors=%d %.1fs",
            report.created,
            report.updated,
            report.deleted,
            len(report.errors),
            report.elapsed_seconds,
        )
        return report

    async def sync_year(self, year: int) -> SyncReport:
        """Sync events for a single calendar year only."""
        report = SyncReport()
        logger.info("Calendar Sync Year Started: %d", year)

        if self._adapter:
            await self._sync_year_games(year, report)
            await self._sync_seasonal_events(year, report)

        report.finished_at = datetime.now(UTC)
        logger.info(
            "Calendar Sync Year %d Finished — created=%d updated=%d",
            year,
            report.created,
            report.updated,
        )
        return report

    # ------------------------------------------------------------------
    # Sale events (legacy stub)
    # ------------------------------------------------------------------

    async def sync_sale_events(self) -> int:
        """Sync upcoming sales from providers into calendar events.

        Legacy stub — returns 0.  Full sale sync is not yet implemented.
        """
        # TODO: Cross-reference roadmap phase 17 — collect from providers
        return 0

    # ------------------------------------------------------------------
    # Reminders
    # ------------------------------------------------------------------

    async def check_reminders(self) -> list[dict[str, Any]]:
        """Check for events ending within the next 2 hours.

        Legacy stub — returns an empty list.
        """
        return []

    async def send_reminders(self, start: datetime, end: datetime) -> int:
        """Send reminders for events ending in *start*-*end*.

        Legacy stub — returns 0.
        """
        return 0

    # ------------------------------------------------------------------
    # Event-level operations (delegated to adapter)
    # ------------------------------------------------------------------

    async def create_event(
        self,
        *,
        title: str,
        start: str,
        end: str,
        reminder_minutes: int = 60,
    ) -> str | None:
        """Create a single calendar event. Returns the event ID or None."""
        if not self._adapter:
            return None
        try:
            return await self._adapter.create_event(
                title=title,
                start=start,
                end=end,
                reminder_minutes=reminder_minutes,
            )
        except Exception as exc:
            logger.warning("Failed to create event: %s", exc)
            return None

    async def update_event(  # noqa: PLR0913
        self,
        event_id: str,
        *,
        title: str,
        start: str,
        end: str,
        reminder_minutes: int = 60,
        color_id: int | None = None,
    ) -> bool:
        """Update an existing calendar event. Returns True on success."""
        if not self._adapter:
            return False
        try:
            await self._adapter.update_event(
                event_id,
                title=title,
                start=start,
                end=end,
                reminder_minutes=reminder_minutes,
                color_id=color_id,
            )
            return True
        except Exception as exc:
            logger.warning("Failed to update event %s: %s", event_id, exc)
            return False

    async def delete_event(self, event_id: str) -> bool:
        """Delete a calendar event by its Google event ID."""
        if not self._adapter:
            return False
        try:
            await self._adapter.delete_event(event_id)
            return True
        except Exception as exc:
            logger.warning("Failed to delete event %s: %s", event_id, exc)
            return False

    async def find_events_by_ext_id(self, ext_id: str) -> list[dict[str, Any]]:
        """Search for calendar events whose extendedProperties contains *ext_id*."""
        if not self._adapter:
            return []
        try:
            return await self._adapter.find_events_by_ext_id(ext_id)
        except Exception as exc:
            logger.warning("Failed to find events by ext_id %s: %s", ext_id, exc)
            return []

    async def delete_past_events(self) -> int:
        """Remove all calendar events whose date is before today."""
        if not self._adapter:
            return 0
        today = date.today().isoformat()
        deleted = 0
        try:
            events = await self._adapter.list_events_in_range("1970-01-01", today)
            for event in events:
                eid = event.get("id", "")
                try:
                    await self._adapter.delete_event(eid)
                    deleted += 1
                except Exception as exc:
                    logger.warning("Failed to delete event %s: %s", eid, exc)
        except Exception as exc:
            logger.warning("Failed to list past events: %s", exc)
        return deleted

    # ------------------------------------------------------------------
    # Internal sync helpers
    # ------------------------------------------------------------------

    async def _sync_year_games(self, year: int, report: SyncReport) -> None:
        """Sync all known game releases for *year*."""
        if not self._new_releases:
            report.errors.append("NewReleasesService not available")
            return

        result = await self._safe_call(
            self._new_releases.get_year_releases(year, limit=500),
            f"get_year_releases({year})",
        )
        if not result or not result.games:
            logger.info("Calendar Sync Year %d: no releases found", year)
            return

        logger.info("Calendar Sync Year %d: %d releases found", year, len(result.games))

        for game in result.games:
            await self._sync_one_game(game, report)

    async def _sync_one_game(self, game: Any, report: SyncReport) -> None:
        """Sync a single game to Google Calendar (create or update)."""
        if not game.release_date or not self._adapter:
            return

        ext_id = f"{_PREFIX_COMING_SOON}-{game.id}"
        title = f"\U0001f3ae {game.title}"
        date_str = game.release_date.isoformat()
        reminder = self._settings.google_calendar_default_reminder_minutes

        existing = await self._safe_call(
            self._adapter.find_events_by_ext_id(ext_id),
            "find_events_by_ext_id",
        )

        try:
            if existing:
                eid = existing[0].get("id", "")
                await self._adapter.update_event(
                    eid,
                    title=title,
                    start=date_str,
                    end=date_str,
                    reminder_minutes=reminder,
                    color_id=self._settings.google_event_color_releases,
                )
                report.updated += 1
            else:
                eid = await self._adapter.create_event(
                    title=title,
                    start=date_str,
                    end=date_str,
                    reminder_minutes=reminder,
                )
                await self._tag_event(
                    eid,
                    ext_id,
                    "coming-soon",
                    self._settings.google_event_color_releases,
                )
                report.created += 1
        except Exception as exc:
            msg = f"Failed to sync game {game.id} ({game.title}): {exc}"
            logger.warning(msg)
            report.errors.append(msg)

    async def _sync_updates(self, report: SyncReport) -> None:
        """Sync major-update events to Google Calendar."""
        if not self._major_updates or not self._adapter:
            return

        result = await self._safe_call(
            self._major_updates.get_major_updates(limit=200),
            "get_major_updates",
        )
        if not result or not result.updates:
            return

        for update in result.updates:
            ext_id = f"{_PREFIX_UPDATE}-{update.app_id}-{update.title}"
            title = f"\U0001f6e0 {update.game_name} \u2014 {update.update_title}"
            date_str = update.date.strftime("%Y-%m-%d")
            reminder = self._settings.google_calendar_default_reminder_minutes

            existing = await self._safe_call(
                self._adapter.find_events_by_ext_id(ext_id),
                "find_events_by_ext_id",
            )

            try:
                if existing:
                    eid = existing[0].get("id", "")
                    await self._adapter.update_event(
                        eid,
                        title=title,
                        start=date_str,
                        end=date_str,
                        reminder_minutes=reminder,
                        color_id=self._settings.google_event_color_updates,
                    )
                    report.updated += 1
                else:
                    eid = await self._adapter.create_event(
                        title=title,
                        start=date_str,
                        end=date_str,
                        reminder_minutes=reminder,
                    )
                    await self._tag_event(
                        eid,
                        ext_id,
                        "major-update",
                        self._settings.google_event_color_updates,
                    )
                    report.created += 1
            except Exception as exc:
                msg = f"Failed to sync update {ext_id}: {exc}"
                logger.warning(msg)
                report.errors.append(msg)

    async def _sync_seasonal_events(self, year: int, report: SyncReport) -> None:
        """Sync seasonal gaming events (sales, festivals, showcases) for *year*."""
        if not self._adapter:
            return

        events = seasonal_events_for_year(year)
        if not events:
            return

        reminder = self._settings.google_calendar_default_reminder_minutes

        for event in events:
            ext_id = event.external_id
            title = event.title
            start_str = event.start_date.isoformat()
            end_str = event.end_date.isoformat()

            existing = await self._safe_call(
                self._adapter.find_events_by_ext_id(ext_id),
                "find_events_by_ext_id",
            )

            try:
                if existing:
                    eid = existing[0].get("id", "")
                    await self._adapter.update_event(
                        eid,
                        title=title,
                        start=start_str,
                        end=end_str,
                        reminder_minutes=reminder,
                        color_id=event.color_id,
                    )
                    report.updated += 1
                else:
                    eid = await self._adapter.create_event(
                        title=title,
                        start=start_str,
                        end=end_str,
                        reminder_minutes=reminder,
                    )
                    await self._tag_event(eid, ext_id, "seasonal", event.color_id)
                    report.created += 1
            except Exception as exc:
                msg = f"Failed to sync seasonal event {ext_id}: {exc}"
                logger.warning(msg)
                report.errors.append(msg)

    async def _tag_event(
        self,
        event_id: str,
        ext_id: str,
        source: str,
        color_id: int,
    ) -> None:
        """Attach externalId and colour to an already-created event."""
        if not self._adapter:
            return
        try:
            await self._adapter._run(
                self._adapter._service.events().patch(
                    calendarId=self._adapter._calendar_id,
                    eventId=event_id,
                    body={
                        "extendedProperties": {
                            "private": {
                                _EXT_ID_KEY: ext_id,
                                _EXT_SOURCE_KEY: source,
                            },
                        },
                        "colorId": str(color_id),
                    },
                ),
            )
        except Exception as exc:
            logger.warning("Failed to tag event %s: %s", event_id, exc)

    @staticmethod
    async def _safe_call(coro: Any, label: str) -> Any:
        """Await a coroutine, logging but suppressing any exception."""
        try:
            return await coro
        except Exception as exc:
            logger.exception("Calendar service error in %s: %s", label, exc)
            return None
