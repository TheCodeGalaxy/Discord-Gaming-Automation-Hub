"""HMAC webhook signature verification for n8n automation.

n8n signs every webhook request with HMAC-SHA256 using the shared
``N8N_WEBHOOK_SECRET``. This module verifies the signature before the
request reaches the scheduler.
"""

from __future__ import annotations

import hashlib
import hmac
import logging

logger = logging.getLogger(__name__)


def verify_webhook_signature(payload: bytes, signature: str, secret: str) -> bool:
    """Verify HMAC-SHA256 signature of the raw request body.

    Args:
        payload: Raw request body bytes.
        signature: The ``X-Hub-Signature-256`` header value from n8n.
        secret: The shared ``N8N_WEBHOOK_SECRET``.

    Returns:
        True when the signature is valid, False otherwise.
    """
    if not secret:
        logger.warning("N8N_WEBHOOK_SECRET is not configured — rejecting all signatures")
        return False
    if not signature:
        return False
    expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)
