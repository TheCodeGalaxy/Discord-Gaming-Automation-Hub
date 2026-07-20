"""JobScheduler — dispatch n8n-triggered calendar actions.

Calendar actions (``calendar_sync``, ``calendar_reminders``) remain
driven by n8n webhooks. Poster channels use the internal
``ChannelScheduler`` instead.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Coroutine
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from gaming_hub.core.exceptions import ProviderError

if TYPE_CHECKING:
    from gaming_hub.services.calendar_service import CalendarService

logger = logging.getLogger(__name__)

Handler = Callable[[dict[str, Any]], Coroutine[Any, Any, dict[str, Any]]]


class JobScheduler:
    """Dispatch n8n-triggered calendar actions.

    Initialised with an optional ``CalendarService``. Unknown actions
    raise ``ValueError``. Poster channel scheduling no longer passes
    through this class.
    """

    def __init__(
        self,
        calendar_service: CalendarService | None = None,
    ) -> None:
        """Initialize the scheduler with an optional calendar service."""
        self._calendar_service = calendar_service

        self._handlers: dict[str, Handler] = {
            "calendar_sync": self._calendar_sync,
            "calendar_reminders": self._calendar_reminders,
        }

    async def dispatch(self, action: str, data: dict[str, Any] | None = None) -> dict[str, Any]:
        """Dispatch an n8n action to its handler.

        Args:
            action: The action name (e.g. ``calendar_sync``).
            data: Optional parameters forwarded to the handler.

        Returns:
            A result dict with at minimum a ``success`` boolean.

        Raises:
            ValueError: If the action is not registered.
        """
        handler = self._handlers.get(action)
        if not handler:
            raise ValueError(f"Unknown action: {action}")
        logger.info("Dispatching action: %s", action)
        payload = dict(data or {})
        payload["_action"] = action
        return await handler(payload)

    # ------------------------------------------------------------------
    # Calendar handlers
    # ------------------------------------------------------------------

    async def _calendar_sync(self, data: dict[str, Any]) -> dict[str, Any]:
        if not self._calendar_service:
            return {"success": False, "error": "Calendar service not configured"}
        try:
            result = await self._calendar_service.sync()
            return {"success": True, "events_synced": result}
        except (ProviderError, Exception) as e:
            logger.exception("Calendar sync failed")
            return {"success": False, "error": str(e)}

    async def _calendar_reminders(self, data: dict[str, Any]) -> dict[str, Any]:
        if not self._calendar_service:
            return {"success": False, "error": "Calendar service not configured"}
        try:
            now = datetime.now(UTC)
            window_end = now + timedelta(hours=1)
            sent = await self._calendar_service.send_reminders(now, window_end)
            return {"success": True, "reminders_sent": sent}
        except (ProviderError, Exception) as e:
            logger.exception("Calendar reminders failed")
            return {"success": False, "error": str(e)}
