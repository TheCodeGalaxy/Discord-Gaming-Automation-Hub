"""Sale / calendar event ORM model."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from gaming_hub.data.database.models.base import Base


class SaleModel(Base):
    """Cached seasonal sale or major promotional event."""

    __tablename__ = "sales"

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    store: Mapped[str | None] = mapped_column(String(64), nullable=True)

    starts_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    url: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    calendar_event_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    reminder_minutes: Mapped[int] = mapped_column(Integer, default=60)

    created_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(UTC).replace(tzinfo=None),
    )

    def __repr__(self) -> str:
        """Return a developer-friendly string representation."""
        return f"<SaleModel id={self.id!r} title={self.title!r}>"
