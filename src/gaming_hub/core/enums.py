"""Domain enumerations.

Enums keep the codebase free of magic strings and provide type-safe
branching across providers, stores, and game categories.
"""

from __future__ import annotations

from enum import StrEnum, auto


class ProviderName(StrEnum):
    """Supported gaming data providers."""

    CheapShark = "cheapshark"
    Epic = "epic"
    SteamCommunity = "steam_community"
    IsThereAnyDeal = "isthereanydeal"
    Rawg = "rawg"


class StoreName(StrEnum):
    """Digital game stores referenced by providers."""

    Steam = "steam"
    Epic = "epic"
    GOG = "gog"
    Itch = "itch"
    Humble = "humble"
    Fanatical = "fanatical"
    GreenManGaming = "greenman_gaming"
    Origin = "origin"
    Microsoft = "microsoft"
    Ubisoft = "ubisoft"
    Unknown = "unknown"


class MediaType(StrEnum):
    """Types of game-related media assets."""

    Cover = auto()
    Banner = auto()
    Logo = auto()
    Screenshot = auto()
    Trailer = auto()


class UpdateType(StrEnum):
    """Categories of game updates used by #major-updates filtering."""

    DLC = "dlc"
    Expansion = "expansion"
    Season = "season"
    MajorUpdate = "major_update"
    Patch = "patch"


class EventType(StrEnum):
    """Calendar event types."""

    SteamSale = "steam_sale"
    EpicSale = "epic_sale"
    GameRelease = "game_release"
    FreeGameExpiry = "free_game_expiry"
