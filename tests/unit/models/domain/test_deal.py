"""Tests for Deal domain entity."""

from __future__ import annotations

from datetime import datetime

import pytest
from pydantic import ValidationError

from gaming_hub.core.enums import StoreName
from gaming_hub.models.domain.deal import Deal


class TestDeal:
    """Deal entity construction and validation."""

    @pytest.mark.unit
    def test_minimal_construction(self) -> None:
        """Deal should construct with only required fields."""
        price = 9.99
        deal = Deal(id="d1", title="Test Deal", current_price=price)
        assert deal.id == "d1"
        assert deal.title == "Test Deal"
        assert deal.current_price == price
        assert deal.store == StoreName.Unknown
        assert deal.currency == "USD"
        assert deal.discount_percent == 0.0
        assert deal.is_free is False

    @pytest.mark.unit
    def test_full_construction(self) -> None:
        """Deal should construct with all optional fields."""
        deal = Deal(
            id="d2",
            game_id="g1",
            title="Full Deal",
            store=StoreName.Steam,
            store_url="https://store.steampowered.com/app/12345",
            currency="EUR",
            current_price=19.99,
            original_price=59.99,
            discount_percent=66.7,
            historical_low_price=14.99,
            historical_low_store=StoreName.Fanatical,
            is_historical_low=False,
            deal_started_at=datetime(2026, 6, 1),
            deal_ends_at=datetime(2026, 7, 1),
            provider_names=["cheapshark"],
            provider_url="https://cheapshark.com/deal/123",
            is_free=False,
        )
        assert deal.store == StoreName.Steam
        assert deal.currency == "EUR"
        assert deal.discount_percent == pytest.approx(66.7)
        assert deal.provider_names == ["cheapshark"]

    @pytest.mark.unit
    def test_price_must_be_positive(self) -> None:
        """Deal should reject negative current_price."""
        with pytest.raises(ValidationError):
            Deal(id="d3", title="Neg", current_price=-1.0)

    @pytest.mark.unit
    def test_discount_bounds(self) -> None:
        """Deal should reject out-of-range discount_percent."""
        with pytest.raises(ValidationError):
            Deal(id="d4", title="Over", current_price=10.0, discount_percent=101)
        with pytest.raises(ValidationError):
            Deal(id="d5", title="Under", current_price=10.0, discount_percent=-1)

    @pytest.mark.unit
    def test_json_roundtrip(self) -> None:
        """Deal should survive JSON serialization roundtrip."""
        discount = 75.0
        deal = Deal(
            id="d6",
            title="Roundtrip",
            current_price=4.99,
            original_price=19.99,
            discount_percent=discount,
            store=StoreName.Epic,
        )
        data = deal.model_dump_json()
        restored = Deal.model_validate_json(data)
        assert restored == deal
        assert restored.store == StoreName.Epic
        assert restored.discount_percent == discount

    @pytest.mark.unit
    def test_free_deal_defaults(self) -> None:
        """Deal with zero price and is_free should construct."""
        deal = Deal(id="d7", title="Free", current_price=0.0, is_free=True)
        assert deal.is_free is True
        assert deal.current_price == 0.0

    @pytest.mark.unit
    def test_missing_id_raises(self) -> None:
        """Deal should raise ValidationError when id is missing."""
        with pytest.raises(ValidationError):
            Deal(title="No ID", current_price=5.0)  # type: ignore[call-arg]

    @pytest.mark.unit
    def test_missing_current_price_raises(self) -> None:
        """Deal should raise ValidationError when current_price is missing."""
        with pytest.raises(ValidationError):
            Deal(id="d8", title="No Price")  # type: ignore[call-arg]
