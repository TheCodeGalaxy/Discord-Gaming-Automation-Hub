"""Sale / calendar event domain entity."""

from datetime import datetime

from pydantic import BaseModel, Field, HttpUrl

from gaming_hub.core.enums import EventType, StoreName


class Sale(BaseModel):
    """Normalized seasonal sale or major promotional event."""

    id: str = Field(..., description="Stable identifier for the event.")
    title: str
    event_type: EventType
    store: StoreName | None = Field(default=None)

    starts_at: datetime
    ends_at: datetime | None = Field(default=None)

    description: str | None = Field(default=None)
    url: HttpUrl | None = Field(default=None)

    # Calendar integration
    calendar_event_id: str | None = Field(default=None)
    reminder_minutes: int = Field(default=60, ge=0)
