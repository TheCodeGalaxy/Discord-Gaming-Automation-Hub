"""Inbound request DTOs."""

from typing import Any

from pydantic import BaseModel, Field

from gaming_hub.core.enums import ProviderName, StoreName


class SearchRequest(BaseModel):
    """Unified search request accepted by providers and services."""

    query: str = Field(default="", description="Free-text search query.")
    steam_app_id: int | None = Field(default=None, description="Direct Steam App ID lookup.")
    providers: list[ProviderName] = Field(
        default_factory=list,
        description="Providers to query. Empty means use all enabled providers.",
    )
    stores: list[StoreName] = Field(default_factory=list)
    genres: list[str] = Field(default_factory=list)
    min_discount: int | None = Field(default=None, ge=0, le=100)
    max_price: float | None = Field(default=None, ge=0)
    only_free: bool = Field(default=False)
    upcoming: bool = Field(default=False)
    exact: bool = Field(default=False)
    limit: int = Field(default=10, ge=1, le=200)
    offset: int = Field(default=0, ge=0)


class WebhookPayload(BaseModel):
    """Payload sent by n8n or external schedulers to trigger automations."""

    job_name: str = Field(..., description="Name of the automation job to trigger.")
    channel_id: int | None = Field(default=None)
    dry_run: bool = Field(default=False)
    parameters: dict[str, Any] = Field(default_factory=dict)
