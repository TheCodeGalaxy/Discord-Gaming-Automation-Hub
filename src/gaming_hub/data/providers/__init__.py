"""External gaming data provider adapters."""

from gaming_hub.core.interfaces import DataProvider
from gaming_hub.data.providers.registry import ProviderRegistry

__all__ = ["DataProvider", "ProviderRegistry"]
