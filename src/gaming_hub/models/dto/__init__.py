"""Data-transfer objects used across layers and external boundaries."""

from gaming_hub.models.dto.provider import ProviderMetadata, ProviderResult
from gaming_hub.models.dto.request import SearchRequest, WebhookPayload

__all__ = ["ProviderMetadata", "ProviderResult", "SearchRequest", "WebhookPayload"]
