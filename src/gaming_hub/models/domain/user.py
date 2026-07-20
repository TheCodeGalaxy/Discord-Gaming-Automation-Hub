"""User preference domain entity."""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field


class UserPreferences(BaseModel):
    """Per-user Discord settings and recommendation profile.

    The default instance is derived from the global ``.env`` configuration.
    Future phases may persist overrides per Discord user.
    """

    discord_user_id: int | None = Field(default=None)
    favorite_genres: list[str] = Field(default_factory=list)
    ignored_stores: list[str] = Field(default_factory=list)
    ignored_tags: list[str] = Field(default_factory=list)
    surprise_history: list[str] = Field(
        default_factory=list,
        description="Game IDs previously suggested by /surprise.",
    )
    discount_threshold: int = Field(default=50, ge=0, le=100)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC).replace(tzinfo=None))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC).replace(tzinfo=None))
