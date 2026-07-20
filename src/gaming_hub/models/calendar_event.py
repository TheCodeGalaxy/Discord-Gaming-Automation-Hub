"""Calendar event domain entity.

Represents a single scheduled event that can be synced to a Google Calendar,
such as a seasonal sale or a game release.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import date, datetime

    from gaming_hub.core.enums import EventType


class CalendarEvent:
    """A sale, release, or expiry that gets synced to Google Calendar.

    Attributes:
        summary: Human-readable title (e.g. "Steam Summer Sale").
        description: Event details for the calendar body.
        start_date: Event start (date for all-day, datetime for timed).
        end_date: Event end (date for all-day, datetime for timed).
        event_type: Categorisation from ``EventType``.
        source: Provider name that sourced the event (e.g. "cheapshark").
        external_id: Stable identifier from the source provider.
    """

    def __init__(  # noqa: PLR0913
        self,
        summary: str,
        description: str,
        start_date: date | datetime,
        end_date: date | datetime,
        event_type: EventType,
        source: str,
        external_id: str,
    ) -> None:
        """Initialize a CalendarEvent."""
        self.summary = summary
        self.description = description
        self.start_date = start_date
        self.end_date = end_date
        self.event_type = event_type
        self.source = source
        self.external_id = external_id
