"""Application services (use cases).

Each module encapsulates one bot feature or automation workflow. Services
depend only on domain interfaces and the domain model; they do not know
whether data originates from CheapShark, Epic, Discord, or cache.
"""

from gaming_hub.services.calendar_service import CalendarService
from gaming_hub.services.discount_service import DiscountResult, DiscountService
from gaming_hub.services.free_games_service import FreeGamesResult, FreeGamesService
from gaming_hub.services.history import InMemoryHistoryTracker
from gaming_hub.services.major_updates_service import (
    GameUpdate,
    MajorUpdatesResult,
    MajorUpdatesService,
)
from gaming_hub.services.new_releases_service import (
    NewReleasesResult,
    NewReleasesService,
)
from gaming_hub.services.search_service import AutocompleteItem, SearchResult, SearchService
from gaming_hub.services.surprise_service import SurpriseResult, SurpriseService
from gaming_hub.services.top_games_service import (
    GameSignal,
    ScoredGame,
    ScoringWeights,
    TopGamesResult,
    TopGamesService,
)

__all__ = [
    "AutocompleteItem",
    "CalendarService",
    "DiscountResult",
    "DiscountService",
    "FreeGamesResult",
    "FreeGamesService",
    "GameSignal",
    "GameUpdate",
    "InMemoryHistoryTracker",
    "MajorUpdatesResult",
    "MajorUpdatesService",
    "NewReleasesResult",
    "NewReleasesService",
    "ScoredGame",
    "ScoringWeights",
    "SearchResult",
    "SearchService",
    "SurpriseResult",
    "SurpriseService",
    "TopGamesResult",
    "TopGamesService",
]
