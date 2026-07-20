"""n8n webhook router — HMAC-authenticated dispatch to calendar services.

n8n calendar workflows POST to this endpoint with an ``X-Hub-Signature-256``
header. The router verifies the HMAC signature, then delegates to the
``JobScheduler`` for action dispatch. Poster channel scheduling uses the
internal ``ChannelScheduler`` instead.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, HTTPException, Request

from gaming_hub.automation.webhooks import verify_webhook_signature

if TYPE_CHECKING:
    from gaming_hub.automation.scheduler import JobScheduler

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

_scheduler: JobScheduler | None = None
_secret: str = ""


def init_webhooks(scheduler: JobScheduler, n8n_secret: str) -> None:
    """Inject the job scheduler and shared secret at startup.

    Args:
        scheduler: A ``JobScheduler`` instance wired to posters and services.
        n8n_secret: The ``N8N_WEBHOOK_SECRET`` for HMAC verification.
    """
    global _scheduler, _secret  # noqa: PLW0603
    _scheduler = scheduler
    _secret = n8n_secret


@router.post("/n8n")
async def n8n_webhook(request: Request) -> dict[str, Any]:
    """Dispatch a verified n8n job to the scheduler.

    The request must include an ``X-Hub-Signature-256`` header containing the
    HMAC-SHA256 hex digest of the raw body, computed with the shared secret.

    The JSON body must contain:
        ``action`` (str): The job action name (e.g. ``post_free_this_week``).
        ``data`` (dict, optional): Parameters forwarded to the handler.

    Returns:
        A dict with action result fields.

    Raises:
        HTTPException 401: Missing or invalid signature.
        HTTPException 400: Missing ``action`` field.
        HTTPException 503: Scheduler not initialised.
    """
    raw_body: bytes = await request.body()

    signature = request.headers.get("x-hub-signature-256", "")
    if not verify_webhook_signature(raw_body, signature, _secret):
        import hashlib
        import hmac as hmac_mod
        expected = hmac_mod.new(_secret.encode(), raw_body, hashlib.sha256).hexdigest()
        logger.error(
            "HMAC verification failed\n"
            "  raw_body_bytes:          %s\n"
            "  decoded_body:            %s\n"
            "  X-Hub-Signature-256:     %s\n"
            "  expected_signature:      %s\n"
            "  expected_format:         raw hex digest (no 'sha256=' prefix)\n"
            "  hmac.compare_digest():   %s",
            raw_body,
            raw_body.decode(errors="replace"),
            signature,
            expected,
            hmac_mod.compare_digest(expected, signature),
        )
        raise HTTPException(status_code=401, detail="Invalid or missing webhook signature")

    payload: dict[str, Any] = await request.json()
    action: str = payload.get("action", "")
    job_data: dict[str, Any] = payload.get("data", {})

    if not action:
        raise HTTPException(status_code=400, detail="Missing 'action' field")

    if _scheduler is None:
        raise HTTPException(status_code=503, detail="Scheduler not initialized")

    job_data["_action"] = action
    try:
        result = await _scheduler.dispatch(action, job_data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return result
