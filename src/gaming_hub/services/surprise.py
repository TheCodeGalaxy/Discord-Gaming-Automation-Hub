"""Surprise suggestion service.

Planned responsibilities (roadmap phase 15):

- Maintain a rotation history (per user or global).
- Select a random highly-rated game not in recent history.
- Update history after each suggestion.
"""

# TODO: Cross-reference roadmap phase 15 (Surprise & New Releases)

from __future__ import annotations

from gaming_hub.services.base import BaseService


class SurpriseService(BaseService):
    """Placeholder for /surprise use case."""
