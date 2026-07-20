"""Game ORM model."""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import JSON, Boolean, Date, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from gaming_hub.data.database.models.base import Base


class GameModel(Base):
    """Cached normalized game record."""

    __tablename__ = "games"

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    short_description: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    genres: Mapped[list[str]] = mapped_column(JSON, default=list)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    platforms: Mapped[list[str]] = mapped_column(JSON, default=list)

    developers: Mapped[list[str]] = mapped_column(JSON, default=list)
    publishers: Mapped[list[str]] = mapped_column(JSON, default=list)

    release_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    coming_soon_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    steam_app_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    epic_namespace: Mapped[str | None] = mapped_column(String(255), nullable=True)
    gog_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    cover_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    banner_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    metacritic_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    steam_review_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    steam_review_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    provider_name: Mapped[str] = mapped_column(String(128), nullable=False)
    provider_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    is_free: Mapped[bool] = mapped_column(Boolean, default=False)
    free_until: Mapped[date | None] = mapped_column(Date, nullable=True)

    raw_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(UTC).replace(tzinfo=None),
    )
    updated_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(UTC).replace(tzinfo=None),
        onupdate=lambda: datetime.now(UTC).replace(tzinfo=None),
    )

    def __repr__(self) -> str:
        """Return a developer-friendly string representation."""
        return f"<GameModel id={self.id!r} title={self.title!r}>"
