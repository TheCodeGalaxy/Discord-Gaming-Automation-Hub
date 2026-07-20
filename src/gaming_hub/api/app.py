"""FastAPI application factory."""

# TODO: Cross-reference roadmap phase 22 (Web API)

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI

from gaming_hub.api.routers import health, webhooks
from gaming_hub.config.loader import load_settings

logger = logging.getLogger(__name__)


def create_app(scheduler: Any = None, settings_override: Any = None) -> FastAPI:
    """Create and configure the internal FastAPI application.

    Args:
        scheduler: Optional ``JobScheduler`` for n8n calendar webhook dispatch.
            When provided, the webhook router is initialised and included.
            Poster channels are scheduled internally and are not routed here.
        settings_override: Optional ``Settings`` instance to use instead
            of loading from environment (used when the bot is already running).

    Returns:
        Configured ``FastAPI`` instance.
    """
    settings = settings_override or load_settings()

    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description="Internal API for the Discord Gaming Automation Hub.",
        docs_url="/docs" if settings.is_development else None,
        redoc_url="/redoc" if settings.is_development else None,
    )

    app.include_router(health.router, tags=["health"])

    if scheduler is not None:
        secret = settings.n8n_webhook_secret
        masked = secret[:4] + "..." + secret[-4:] if len(secret) > 8 else "(empty)"
        logger.info(
            "n8n webhook secret loaded (backend):  len=%d  value=%s",
            len(secret),
            masked,
        )
        # Instruct user to verify the n8n side:
        #   docker compose exec n8n node -e "console.log(process.env.N8N_WEBHOOK_SECRET)"
        logger.info(
            "Verify n8n secret matches: run `docker compose exec n8n node -e "
            '"console.log(process.env.N8N_WEBHOOK_SECRET)"\'',
        )

        webhooks.init_webhooks(scheduler, secret)
        # The router already defines prefix="/webhooks" + route "/n8n",
        # so the canonical endpoint is /webhooks/n8n.  Do NOT add another
        # prefix — FastAPI appends router prefixes (it does not replace).
        app.include_router(webhooks.router, tags=["webhooks"])

    return app
