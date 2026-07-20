"""Tests for Sale domain entity."""

from __future__ import annotations

from datetime import datetime

import pytest
from pydantic import ValidationError

from gaming_hub.core.enums import EventType, StoreName
from gaming_hub.models.domain.sale import Sale


class TestSale:
    """Sale entity construction and validation."""

    @pytest.mark.unit
    def test_minimal_construction(self) -> None:
        """Sale should construct with only required fields."""
        reminder = 60
        sale = Sale(
            id="s1",
            title="Summer Sale",
            event_type="steam_sale",
            starts_at="2026-07-01T00:00:00Z",
        )
        assert sale.id == "s1"
        assert sale.title == "Summer Sale"
        assert sale.event_type == EventType.SteamSale
        assert sale.store is None
        assert sale.ends_at is None
        assert sale.reminder_minutes == reminder

    @pytest.mark.unit
    def test_full_construction(self) -> None:
        """Sale should construct with all optional fields."""
        reminder = 120
        sale = Sale(
            id="s2",
            title="Epic Mega Sale",
            event_type=EventType.EpicSale,
            store=StoreName.Epic,
            starts_at=datetime(2026, 11, 1, 0, 0, 0),
            ends_at=datetime(2026, 11, 30, 23, 59, 59),
            description="Huge discounts on Epic Games Store",
            url="https://epicgames.com/sale",
            calendar_event_id="cal_123",
            reminder_minutes=reminder,
        )
        assert sale.event_type == EventType.EpicSale
        assert sale.store == StoreName.Epic
        assert sale.reminder_minutes == reminder
        assert sale.calendar_event_id == "cal_123"

    @pytest.mark.unit
    def test_json_roundtrip(self) -> None:
        """Sale should survive JSON serialization roundtrip."""
        sale = Sale(
            id="s3",
            title="Roundtrip",
            event_type="game_release",
            starts_at="2026-12-01T00:00:00Z",
            store="steam",
        )
        data = sale.model_dump_json()
        restored = Sale.model_validate_json(data)
        assert restored == sale
        assert restored.event_type == EventType.GameRelease
        assert restored.store == StoreName.Steam

    @pytest.mark.unit
    def test_enum_string_comparison(self) -> None:
        """EventType enum should support string lookup."""
        assert EventType("epic_sale") == EventType.EpicSale
        assert EventType("free_game_expiry") == EventType.FreeGameExpiry

    @pytest.mark.unit
    def test_reminder_minutes_non_negative(self) -> None:
        """Sale should reject negative reminder_minutes."""
        with pytest.raises(ValidationError):
            Sale(
                id="s4",
                title="Neg",
                event_type="steam_sale",
                starts_at="2026-07-01T00:00:00Z",
                reminder_minutes=-1,
            )

    @pytest.mark.unit
    def test_missing_id_raises(self) -> None:
        """Sale should raise ValidationError when id is missing."""
        with pytest.raises(ValidationError):
            Sale(
                title="No ID",
                event_type="steam_sale",
                starts_at="2026-07-01T00:00:00Z",
            )  # type: ignore[call-arg]
