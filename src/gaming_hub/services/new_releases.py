"""New releases service.

Planned responsibilities (roadmap phase 15):

- Collect games released within ``NEW_RELEASE_DAYS``.
- Filter by provider reliability and signal confidence.
- Build candidates for /new command.
"""

# TODO: Cross-reference roadmap phase 15 (Surprise & New Releases)

from __future__ import annotations

from gaming_hub.services.base import BaseService


class NewReleasesService(BaseService):
    """Placeholder for /new use case."""
