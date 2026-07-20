"""Search service.

Planned responsibilities (roadmap phase 12):

- Accept unified ``SearchRequest``.
- Fan out queries to enabled providers in parallel.
- Merge, deduplicate, and rank results.
- Return provider-agnostic list of ``Game`` / ``Deal`` objects with metadata.
"""

# TODO: Cross-reference roadmap phase 12 (Search Service)

from __future__ import annotations

from gaming_hub.services.base import BaseService


class SearchService(BaseService):
    """Placeholder for unified search use case."""
