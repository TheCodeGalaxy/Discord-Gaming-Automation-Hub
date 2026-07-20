"""Tests for request DTOs."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from gaming_hub.core.enums import ProviderName, StoreName
from gaming_hub.models.dto.request import SearchRequest, WebhookPayload


class TestSearchRequest:
    """SearchRequest construction and defaults."""

    @pytest.mark.unit
    def test_default_construction(self) -> None:
        """SearchRequest should provide sensible defaults."""
        default_limit = 10
        req = SearchRequest()
        assert req.query == ""
        assert req.providers == []
        assert req.stores == []
        assert req.genres == []
        assert req.min_discount is None
        assert req.max_price is None
        assert req.only_free is False
        assert req.upcoming is False
        assert req.limit == default_limit
        assert req.offset == 0

    @pytest.mark.unit
    def test_query_construction(self) -> None:
        """SearchRequest should accept a query string."""
        req = SearchRequest(query="RPG")
        assert req.query == "RPG"

    @pytest.mark.unit
    def test_full_construction(self) -> None:
        """SearchRequest should construct with all fields."""
        provider_count = 2
        min_discount = 50
        req_limit = 25
        req_offset = 5
        req = SearchRequest(
            query="cyberpunk",
            providers=[ProviderName.CheapShark, ProviderName.SteamCommunity],
            stores=[StoreName.Steam, StoreName.GOG],
            genres=["RPG", "Open World"],
            min_discount=min_discount,
            max_price=29.99,
            only_free=False,
            upcoming=True,
            limit=req_limit,
            offset=req_offset,
        )
        assert req.query == "cyberpunk"
        assert len(req.providers) == provider_count
        assert ProviderName.CheapShark in req.providers
        assert req.min_discount == min_discount
        assert req.limit == req_limit
        assert req.offset == req_offset

    @pytest.mark.unit
    def test_limit_bounds(self) -> None:
        """SearchRequest should reject out-of-range limit."""
        with pytest.raises(ValidationError):
            SearchRequest(limit=0)
        with pytest.raises(ValidationError):
            SearchRequest(limit=201)

    @pytest.mark.unit
    def test_json_roundtrip(self) -> None:
        """SearchRequest should survive JSON serialization roundtrip."""
        provider_count = 2
        req = SearchRequest(
            query="RPG",
            providers=["cheapshark", "epic"],
            min_discount=30,
        )
        data = req.model_dump_json()
        restored = SearchRequest.model_validate_json(data)
        assert restored == req
        assert len(restored.providers) == provider_count

    @pytest.mark.unit
    def test_enum_serialization(self) -> None:
        """SearchRequest should serialize enum fields to strings."""
        req = SearchRequest(providers=["cheapshark"])
        data = req.model_dump()
        assert data["providers"] == ["cheapshark"]


class TestWebhookPayload:
    """WebhookPayload construction and defaults."""

    @pytest.mark.unit
    def test_minimal_construction(self) -> None:
        """WebhookPayload should construct with only job_name."""
        wp = WebhookPayload(job_name="daily_free_games")
        assert wp.job_name == "daily_free_games"
        assert wp.channel_id is None
        assert wp.dry_run is False
        assert wp.parameters == {}

    @pytest.mark.unit
    def test_full_construction(self) -> None:
        """WebhookPayload should construct with all optional fields."""
        channel_id = 123456789
        wp = WebhookPayload(
            job_name="check_deals",
            channel_id=channel_id,
            dry_run=True,
            parameters={"min_discount": 50},
        )
        min_discount = 50
        assert wp.channel_id == channel_id
        assert wp.dry_run is True
        assert wp.parameters["min_discount"] == min_discount

    @pytest.mark.unit
    def test_json_roundtrip(self) -> None:
        """WebhookPayload should survive JSON roundtrip."""
        wp = WebhookPayload(job_name="test", dry_run=True)
        data = wp.model_dump_json()
        restored = WebhookPayload.model_validate_json(data)
        assert restored == wp

    @pytest.mark.unit
    def test_missing_job_name_raises(self) -> None:
        """WebhookPayload should raise ValidationError when job_name is missing."""
        with pytest.raises(ValidationError):
            WebhookPayload()  # type: ignore[call-arg]
