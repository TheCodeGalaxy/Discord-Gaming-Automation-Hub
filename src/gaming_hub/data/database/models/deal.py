"""Deal ORM model."""

from __future__ import annotations

from datetime import UTC, date, datetime

from sqlalchemy import JSON, Boolean, Date, DateTime, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from gaming_hub.data.database.models.base import Base


class DealModel(Base):
    """Cached deal/discount snapshot."""

    __tablename__ = "deals"

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    game_id: Mapped[str | None] = mapped_column(
        String(255), ForeignKey("games.id"), nullable=True,
    )
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    store: Mapped[str] = mapped_column(String(64), nullable=False, default="unknown")
    store_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    currency: Mapped[str] = mapped_column(String(16), default="USD")
    current_price: Mapped[float] = mapped_column(Float, nullable=False)
    original_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    discount_percent: Mapped[float] = mapped_column(Float, default=0.0)

    historical_low_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_historical_low: Mapped[bool] = mapped_column(Boolean, default=False)

    deal_started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    deal_ends_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    provider_names: Mapped[list[str]] = mapped_column(JSON, default=list)

    is_free: Mapped[bool] = mapped_column(Boolean, default=False)
    free_until: Mapped[date | None] = mapped_column(Date, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(UTC).replace(tzinfo=None),
    )

    def __repr__(self) -> str:
        """Return a developer-friendly string representation."""
        return f"<DealModel id={self.id!r} title={self.title!r}>"
