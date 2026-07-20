"""Settings loader.

Exposes a single entry point so the bootstrap layer never depends on
pydantic-settings directly outside this module.
"""

from __future__ import annotations

import functools

from gaming_hub.config.models import Settings


@functools.lru_cache(maxsize=1)
def load_settings() -> Settings:
    """Load and cache application settings.

    The result is cached so repeated calls during runtime return the same object.
    Use ``load_settings.cache_clear()`` in tests when environment changes.

    Returns:
        Validated ``Settings`` instance.
    """
    return Settings()
