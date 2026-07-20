"""Cache key generation utilities.

Keys follow the pattern: ``{provider}:{method}:{param_hash}``
"""

from __future__ import annotations

import hashlib
from typing import Any


def make_cache_key(provider: str, method: str, /, **params: Any) -> str:
    """Generate a deterministic cache key from provider, method, and params.

    Args:
        provider: Provider name (e.g. ``"cheapshark"``).
        method: Method name (e.g. ``"search"``).
        **params: Normalized keyword arguments used by the method.
                 ``None`` values are excluded. Order does not matter.

    Returns:
        Short string key: ``{provider}:{method}:{12-char hex hash}``.
    """
    sorted_params = sorted(
        (k, v) for k, v in params.items() if v is not None
    )
    param_str = "&".join(f"{k}={v}" for k, v in sorted_params)
    param_hash = hashlib.sha256(param_str.encode()).hexdigest()[:12]
    return f"{provider}:{method}:{param_hash}"
