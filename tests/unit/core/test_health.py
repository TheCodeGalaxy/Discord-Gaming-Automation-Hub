"""Tests for the health endpoint."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from gaming_hub.api.app import create_app


@pytest.mark.unit
def test_health_endpoint_returns_ok() -> None:
    """Health endpoint should return status ok."""
    app = create_app()
    with TestClient(app) as client:
        response = client.get("/health")
    http_200_ok = 200
    assert response.status_code == http_200_ok
    data = response.json()
    assert data["status"] == "ok"
    assert "version" in data
