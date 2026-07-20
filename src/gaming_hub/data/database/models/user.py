"""User preferences ORM model."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import JSON, Integer
from sqlalchemy.orm import Mapped, mapped_column

from gaming_hub.data.database.models.base import Base


class UserPreferencesModel(Base):
    """Per-Discord-user settings and recommendation profile."""

    __tablename__ = "user_preferences"

    discord_user_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    favorite_genres: Mapped[list[str]] = mapped_column(JSON, default=list)
    ignored_stores: Mapped[list[str]] = mapped_column(JSON, default=list)
    ignored_tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    surprise_history: Mapped[list[str]] = mapped_column(JSON, default=list)

    discount_threshold: Mapped[int] = mapped_column(Integer, default=50)

    created_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(UTC).replace(tzinfo=None),
    )
    updated_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(UTC).replace(tzinfo=None),
        onupdate=lambda: datetime.now(UTC).replace(tzinfo=None),
    )

    def __repr__(self) -> str:
        """Return a developer-friendly string representation."""
        return f"<UserPreferencesModel discord_user_id={self.discord_user_id!r}>"
