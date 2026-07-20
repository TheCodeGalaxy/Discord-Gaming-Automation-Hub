"""Game domain entity."""

from datetime import date
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from gaming_hub.core.enums import MediaType


class MediaAsset(BaseModel):
    """A single media asset attached to a game."""

    type: MediaType
    url: HttpUrl
    width: int | None = None
    height: int | None = None


class Game(BaseModel):
    """Normalized game entity produced by provider adapters.

    Providers return heterogeneous data; each adapter maps its native payload
    into this shared shape. Fields should remain optional where providers cannot
    guarantee their presence.
    """

    id: str = Field(..., description="Stable unique identifier (preferably provider-agnostic).")
    title: str = Field(..., description="Canonical game title.")
    description: str | None = Field(default=None)
    short_description: str | None = Field(default=None)

    # Categorization
    genres: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    platforms: list[str] = Field(default_factory=list)

    # People / companies
    developers: list[str] = Field(default_factory=list)
    publishers: list[str] = Field(default_factory=list)

    # Dates
    release_date: date | None = Field(default=None)
    coming_soon_date: date | None = Field(default=None)

    # Identities on external stores
    steam_app_id: int | None = Field(default=None)
    epic_namespace: str | None = Field(default=None)
    gog_id: str | None = Field(default=None)

    # Media
    cover_url: HttpUrl | None = Field(default=None)
    banner_url: HttpUrl | None = Field(default=None)
    media: list[MediaAsset] = Field(default_factory=list)

    # Community signals
    metacritic_score: int | None = Field(default=None, ge=0, le=100)
    steam_review_score: float | None = Field(default=None, ge=0, le=100)
    steam_review_count: int | None = Field(default=None, ge=0)

    # Provider provenance
    provider_name: str
    provider_names: list[str] = Field(
        default_factory=list,
        description="All providers that returned this game (populated during merge).",
    )
    provider_url: HttpUrl | None = Field(default=None)
    raw_metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Opaque provider-specific fields preserved for debug/audit.",
    )

    # Free/promotion flags
    is_free: bool = Field(default=False)
    free_until: date | None = Field(default=None)

    model_config = ConfigDict(frozen=False)
