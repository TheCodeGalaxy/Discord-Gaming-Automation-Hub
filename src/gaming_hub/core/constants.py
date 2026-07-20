"""Project-wide constants.

Constants here are pure values that do not depend on environment state.
Environment-tunable values belong in ``gaming_hub.config.models``.
"""

from __future__ import annotations

# Provider identifiers used in registries and logs.
PROVIDER_CHEAPSHARK = "cheapshark"
PROVIDER_EPIC = "epic"
PROVIDER_STEAM_COMMUNITY = "steam_community"
PROVIDER_ISTHEREANYDEAL = "isthereanydeal"

# Default provider order for unified search aggregation.
DEFAULT_PROVIDER_ORDER: tuple[str, ...] = (
    PROVIDER_CHEAPSHARK,
    PROVIDER_EPIC,
    PROVIDER_STEAM_COMMUNITY,
    PROVIDER_ISTHEREANYDEAL,
)

# Date / time formatting standards.
DATE_FORMAT = "%Y-%m-%d"
DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"

# Pagination / rate-limiting defaults when not configured by user.
DEFAULT_RATE_LIMIT_BACKOFF_SECONDS = 1.0
DEFAULT_PROVIDER_TIMEOUT_SECONDS = 30
