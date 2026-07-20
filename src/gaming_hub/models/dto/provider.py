"""DTOs returned by provider adapters."""

from typing import Any

from pydantic import BaseModel, Field

from gaming_hub.models.domain.deal import Deal
from gaming_hub.models.domain.game import Game
from gaming_hub.models.domain.sale import Sale


class ProviderMetadata(BaseModel):
    """Metadata about a provider call."""

    provider: str
    query: str | None = Field(default=None)
    total_available: int | None = Field(default=None)
    returned: int = Field(default=0)
    cached: bool = Field(default=False)
    response_time_ms: float | None = Field(default=None)
    errors: list[dict[str, Any]] = Field(default_factory=list)


class ProviderResult(BaseModel):
    """Container for normalized provider data plus metadata.

    A single provider call may produce games, deals, and/or sales. Fields are
    lists so services can aggregate across multiple providers uniformly.
    """

    games: list[Game] = Field(default_factory=list)
    deals: list[Deal] = Field(default_factory=list)
    sales: list[Sale] = Field(default_factory=list)
    metadata: ProviderMetadata
