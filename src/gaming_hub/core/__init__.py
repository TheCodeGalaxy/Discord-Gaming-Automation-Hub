"""Core primitives shared across all layers.

Contains constants, enums, exceptions, and domain ports (interfaces) that
drive the dependency-inversion design.
"""

from gaming_hub.core.exceptions import GamingHubError, ProviderError

__all__ = ["GamingHubError", "ProviderError"]
