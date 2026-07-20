"""Tests for domain enumerations."""

from __future__ import annotations

import pytest

from gaming_hub.core.enums import EventType, MediaType, ProviderName, StoreName, UpdateType


class TestProviderName:
    """ProviderName enum string behavior."""

    @pytest.mark.unit
    def test_string_lookup(self) -> None:
        """ProviderName should support inverse string lookup."""
        assert ProviderName("cheapshark") == ProviderName.CheapShark
        assert ProviderName("epic") == ProviderName.Epic
        assert ProviderName("steam_community") == ProviderName.SteamCommunity
        assert ProviderName("isthereanydeal") == ProviderName.IsThereAnyDeal

    @pytest.mark.unit
    def test_string_comparison(self) -> None:
        """ProviderName should compare equal to its value string."""
        assert str(ProviderName.CheapShark) == "cheapshark"

    @pytest.mark.unit
    def test_iteration(self) -> None:
        """ProviderName should contain all members."""
        member_count = 5
        names = [p.value for p in ProviderName]
        assert "cheapshark" in names
        assert "epic" in names
        assert "steam_community" in names
        assert "isthereanydeal" in names
        assert "rawg" in names
        assert len(names) == member_count

    @pytest.mark.unit
    def test_invalid_lookup_raises(self) -> None:
        """ProviderName should raise ValueError for invalid names."""
        with pytest.raises(ValueError):
            ProviderName("nonexistent")


class TestStoreName:
    """StoreName enum string behavior."""

    @pytest.mark.unit
    def test_string_lookup(self) -> None:
        """StoreName should support inverse string lookup."""
        assert StoreName("steam") == StoreName.Steam
        assert StoreName("epic") == StoreName.Epic
        assert StoreName("gog") == StoreName.GOG
        assert StoreName("itch") == StoreName.Itch
        assert StoreName("humble") == StoreName.Humble
        assert StoreName("fanatical") == StoreName.Fanatical
        assert StoreName("greenman_gaming") == StoreName.GreenManGaming
        assert StoreName("unknown") == StoreName.Unknown
        assert StoreName("origin") == StoreName.Origin
        assert StoreName("microsoft") == StoreName.Microsoft
        assert StoreName("ubisoft") == StoreName.Ubisoft

    @pytest.mark.unit
    def test_all_members(self) -> None:
        """StoreName should contain all expected members."""
        member_count = 11
        assert len(list(StoreName)) == member_count

    @pytest.mark.unit
    def test_unknown_fallback(self) -> None:
        """StoreName.Unknown should act as fallback value."""
        assert StoreName("unknown") == StoreName.Unknown


class TestMediaType:
    """MediaType enum behavior."""

    @pytest.mark.unit
    def test_auto_values(self) -> None:
        """MediaType should derive values from member names."""
        assert MediaType.Cover.value == "cover"
        assert MediaType.Banner.value == "banner"
        assert MediaType.Logo.value == "logo"
        assert MediaType.Screenshot.value == "screenshot"
        assert MediaType.Trailer.value == "trailer"

    @pytest.mark.unit
    def test_string_lookup(self) -> None:
        """MediaType should support inverse string lookup."""
        assert MediaType("cover") == MediaType.Cover
        assert MediaType("trailer") == MediaType.Trailer

    @pytest.mark.unit
    def test_all_members(self) -> None:
        """MediaType should contain all expected members."""
        member_count = 5
        assert len(list(MediaType)) == member_count


class TestUpdateType:
    """UpdateType enum behavior."""

    @pytest.mark.unit
    def test_string_lookup(self) -> None:
        """UpdateType should support inverse string lookup."""
        assert UpdateType("dlc") == UpdateType.DLC
        assert UpdateType("expansion") == UpdateType.Expansion
        assert UpdateType("season") == UpdateType.Season
        assert UpdateType("major_update") == UpdateType.MajorUpdate
        assert UpdateType("patch") == UpdateType.Patch

    @pytest.mark.unit
    def test_all_members(self) -> None:
        """UpdateType should contain all expected members."""
        member_count = 5
        assert len(list(UpdateType)) == member_count


class TestEventType:
    """EventType enum behavior."""

    @pytest.mark.unit
    def test_string_lookup(self) -> None:
        """EventType should support inverse string lookup."""
        assert EventType("steam_sale") == EventType.SteamSale
        assert EventType("epic_sale") == EventType.EpicSale
        assert EventType("game_release") == EventType.GameRelease
        assert EventType("free_game_expiry") == EventType.FreeGameExpiry

    @pytest.mark.unit
    def test_all_members(self) -> None:
        """EventType should contain all expected members."""
        member_count = 4
        assert len(list(EventType)) == member_count

    @pytest.mark.unit
    def test_json_serialization(self) -> None:
        """EventType should serialize to lowercase string value."""
        assert EventType.SteamSale.value == "steam_sale"
