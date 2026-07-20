"""Domain entities and value objects."""

from gaming_hub.models.domain.deal import Deal
from gaming_hub.models.domain.game import Game, MediaAsset
from gaming_hub.models.domain.sale import Sale
from gaming_hub.models.domain.user import UserPreferences

__all__ = ["Deal", "Game", "MediaAsset", "Sale", "UserPreferences"]
