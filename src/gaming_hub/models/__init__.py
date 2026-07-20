"""Domain models and data-transfer objects."""

from gaming_hub.models.domain.deal import Deal
from gaming_hub.models.domain.game import Game, MediaAsset
from gaming_hub.models.domain.sale import Sale
from gaming_hub.models.domain.user import UserPreferences
from gaming_hub.models.dto.provider import ProviderMetadata, ProviderResult
from gaming_hub.models.dto.request import SearchRequest, WebhookPayload

__all__ = [
    "Deal",
    "Game",
    "MediaAsset",
    "ProviderMetadata",
    "ProviderResult",
    "Sale",
    "SearchRequest",
    "UserPreferences",
    "WebhookPayload",
]
