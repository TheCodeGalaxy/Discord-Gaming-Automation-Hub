"""Configuration layer for the Gaming Hub.

Loads environment-based settings via pydantic-settings and exposes a single,
typed configuration object to the rest of the application.
"""

from gaming_hub.config.loader import load_settings
from gaming_hub.config.models import Settings

__all__ = ["Settings", "load_settings"]
