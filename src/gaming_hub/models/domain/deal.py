"""Deal domain entity."""

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field, HttpUrl

from gaming_hub.core.enums import StoreName


class Deal(BaseModel):
    """Normalized game deal / discount entity."""

    id: str = Field(..., description="Stable identifier for the deal listing.")
    game_id: str | None = Field(default=None)
    title: str
    store: StoreName = Field(default=StoreName.Unknown)
    store_url: HttpUrl | None = Field(default=None)

    # Pricing
    currency: str = Field(default="USD")
    current_price: float = Field(..., ge=0)
    original_price: float | None = Field(default=None, ge=0)
    discount_percent: float = Field(default=0.0, ge=0, le=100)

    # Historical context
    historical_low_price: float | None = Field(default=None, ge=0)
    historical_low_store: StoreName = Field(default=StoreName.Unknown)
    is_historical_low: bool = Field(default=False)

    # Dates
    deal_started_at: datetime | None = Field(default=None)
    deal_ends_at: datetime | None = Field(default=None)
    price_last_updated: datetime | None = Field(default=None)

    # Provider provenance
    provider_names: list[str] = Field(default_factory=list)
    provider_url: HttpUrl | None = Field(default=None)

    # Free-game promotion overlap
    is_free: bool = Field(default=False)
    free_until: date | None = Field(default=None)

    # Provider-specific metadata
    raw_metadata: dict[str, Any] = Field(default_factory=dict)
