"""SQLAlchemy ORM models."""

from gaming_hub.data.database.models.automation_log import AutomationLogModel
from gaming_hub.data.database.models.base import Base
from gaming_hub.data.database.models.deal import DealModel
from gaming_hub.data.database.models.game import GameModel
from gaming_hub.data.database.models.sale import SaleModel
from gaming_hub.data.database.models.user import UserPreferencesModel

ALL_MODELS = [
    AutomationLogModel,
    DealModel,
    GameModel,
    SaleModel,
    UserPreferencesModel,
]

__all__ = [
    "ALL_MODELS",
    "AutomationLogModel",
    "Base",
    "DealModel",
    "GameModel",
    "SaleModel",
    "UserPreferencesModel",
]
