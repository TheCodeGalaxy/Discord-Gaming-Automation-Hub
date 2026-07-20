"""Tests for HMAC webhook signature verification."""

from __future__ import annotations

import hashlib
import hmac

import pytest

from gaming_hub.automation.webhooks import verify_webhook_signature


def _sign(payload: bytes, secret: str) -> str:
    return hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()


@pytest.mark.unit
class TestVerifyWebhookSignature:
    """verify_webhook_signature behavior."""

    def test_valid_signature_returns_true(self) -> None:
        """Valid HMAC-SHA256 signature is accepted."""
        payload = b'{"action": "test"}'
        secret = "my-secret"
        sig = _sign(payload, secret)
        assert verify_webhook_signature(payload, sig, secret) is True

    def test_invalid_signature_returns_false(self) -> None:
        """Invalid signature is rejected."""
        payload = b'{"action": "test"}'
        secret = "my-secret"
        assert verify_webhook_signature(payload, "bad-signature", secret) is False

    def test_empty_secret_returns_false(self) -> None:
        """Empty secret rejects all signatures."""
        payload = b'{"action": "test"}'
        sig = _sign(payload, "some-secret")
        assert verify_webhook_signature(payload, sig, "") is False

    def test_different_secret_returns_false(self) -> None:
        """Wrong secret is rejected."""
        payload = b'{"action": "test"}'
        sig = _sign(payload, "correct-secret")
        assert verify_webhook_signature(payload, sig, "wrong-secret") is False

    def test_empty_signature_returns_false(self) -> None:
        """Empty signature header is rejected."""
        payload = b'{"action": "test"}'
        assert verify_webhook_signature(payload, "", "my-secret") is False

    def test_keccak_is_not_sha256(self) -> None:
        """Ensure HMAC-SHA256 (not Keccak-256) is used."""
        payload = b"hello"
        # If the implementation incorrectly used SHA-3 / Keccak it would not match
        secret = "test"
        py_hmac = _sign(payload, secret)
        our_result = verify_webhook_signature(payload, py_hmac, secret)
        assert our_result is True
