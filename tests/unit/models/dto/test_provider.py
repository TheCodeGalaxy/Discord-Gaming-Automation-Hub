"""Tests for provider result DTOs."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from gaming_hub.models.domain.deal import Deal
from gaming_hub.models.domain.game import Game
from gaming_hub.models.domain.sale import Sale
from gaming_hub.models.dto.provider import ProviderMetadata, ProviderResult


class TestProviderMetadata:
    """ProviderMetadata construction and defaults."""

    @pytest.mark.unit
    def test_minimal_construction(self) -> None:
        """ProviderMetadata should construct with only required fields."""
        returned = 5
        pm = ProviderMetadata(provider="cheapshark", returned=returned)
        assert pm.provider == "cheapshark"
        assert pm.returned == returned
        assert pm.query is None
        assert pm.total_available is None
        assert pm.cached is False
        assert pm.response_time_ms is None
        assert pm.errors == []

    @pytest.mark.unit
    def test_full_construction(self) -> None:
        """ProviderMetadata should construct with all optional fields."""
        response_time = 150.5
        pm = ProviderMetadata(
            provider="epic",
            query="free games",
            total_available=20,
            returned=10,
            cached=True,
            response_time_ms=response_time,
            errors=[{"code": 429, "message": "Rate limited"}],
        )
        assert pm.cached is True
        assert pm.response_time_ms == response_time
        assert len(pm.errors) == 1

    @pytest.mark.unit
    def test_json_roundtrip(self) -> None:
        """ProviderMetadata should survive JSON roundtrip."""
        pm = ProviderMetadata(provider="steam", returned=3, cached=True)
        data = pm.model_dump_json()
        restored = ProviderMetadata.model_validate_json(data)
        assert restored == pm


class TestProviderResult:
    """ProviderResult container construction."""

    @pytest.mark.unit
    def test_minimal_construction(self) -> None:
        """ProviderResult should construct with only required metadata."""
        pm = ProviderMetadata(provider="test", returned=0)
        pr = ProviderResult(metadata=pm)
        assert pr.games == []
        assert pr.deals == []
        assert pr.sales == []
        assert pr.metadata.provider == "test"

    @pytest.mark.unit
    def test_with_games(self) -> None:
        """ProviderResult should accept a list of games."""
        game = Game(id="1", title="Test", provider_name="cheapshark")
        pm = ProviderMetadata(provider="cheapshark", returned=1)
        pr = ProviderResult(games=[game], metadata=pm)
        assert len(pr.games) == 1
        assert pr.games[0].title == "Test"

    @pytest.mark.unit
    def test_with_all_result_types(self) -> None:
        """ProviderResult should accept games, deals, and sales."""
        game = Game(id="g1", title="Game", provider_name="test")
        deal = Deal(id="d1", title="Deal", current_price=5.0)
        sale = Sale(
            id="s1",
            title="Sale",
            event_type="steam_sale",
            starts_at="2026-07-01T00:00:00Z",
        )
        pm = ProviderMetadata(provider="test", returned=3)
        pr = ProviderResult(games=[game], deals=[deal], sales=[sale], metadata=pm)
        assert len(pr.games) == 1
        assert len(pr.deals) == 1
        assert len(pr.sales) == 1

    @pytest.mark.unit
    def test_json_roundtrip(self) -> None:
        """ProviderResult should survive JSON roundtrip."""
        game = Game(id="g2", title="Roundtrip", provider_name="test")
        pm = ProviderMetadata(provider="test", returned=1)
        pr = ProviderResult(games=[game], metadata=pm)
        data = pr.model_dump_json()
        restored = ProviderResult.model_validate_json(data)
        assert restored == pr
        assert restored.games[0].title == "Roundtrip"

    @pytest.mark.unit
    def test_missing_metadata_raises(self) -> None:
        """ProviderResult should reject construction without metadata."""
        with pytest.raises(ValidationError):
            ProviderResult()  # type: ignore[call-arg]
