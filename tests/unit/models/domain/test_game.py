"""Tests for Game and MediaAsset domain entities."""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from gaming_hub.core.enums import MediaType
from gaming_hub.models.domain.game import Game, MediaAsset


class TestMediaAsset:
    """MediaAsset construction and serialization."""

    @pytest.mark.unit
    def test_minimal_construction(self) -> None:
        """MediaAsset should construct with only required fields."""
        asset = MediaAsset(type="cover", url="https://example.com/cover.jpg")
        assert asset.type == MediaType.Cover
        assert str(asset.url) == "https://example.com/cover.jpg"
        assert asset.width is None
        assert asset.height is None

    @pytest.mark.unit
    def test_construction_with_dimensions(self) -> None:
        """MediaAsset should accept optional width/height."""
        width = 1920
        height = 1080
        asset = MediaAsset(
            type="screenshot",
            url="https://example.com/ss.png",
            width=width,
            height=height,
        )
        assert asset.width == width
        assert asset.height == height
        assert asset.type == MediaType.Screenshot

    @pytest.mark.unit
    def test_serialization_roundtrip(self) -> None:
        """MediaAsset should survive JSON roundtrip."""
        asset = MediaAsset(type="banner", url="https://example.com/banner.jpg")
        data = asset.model_dump_json()
        restored = MediaAsset.model_validate_json(data)
        assert asset == restored

    @pytest.mark.unit
    def test_enum_string_comparison(self) -> None:
        """MediaType enum should support string lookup."""
        assert MediaType("cover") == MediaType.Cover
        assert MediaType("trailer") == MediaType.Trailer


class TestGame:
    """Game domain entity construction and validation."""

    @pytest.mark.unit
    def test_minimal_construction(self) -> None:
        """Game should construct with only id, title, provider_name."""
        game = Game(id="1", title="Test Game", provider_name="cheapshark")
        assert game.id == "1"
        assert game.title == "Test Game"
        assert game.provider_name == "cheapshark"
        assert game.genres == []
        assert game.tags == []
        assert game.platforms == []
        assert game.developers == []
        assert game.publishers == []
        assert game.media == []
        assert game.is_free is False

    @pytest.mark.unit
    def test_full_construction(self) -> None:
        """Game should construct with all optional fields."""
        game = Game(
            id="2",
            title="Full Game",
            description="A game with all fields",
            short_description="Short",
            genres=["RPG", "Action"],
            tags=["singleplayer", "co-op"],
            platforms=["PC", "PS5"],
            developers=["Dev Studio"],
            publishers=["Pub Corp"],
            release_date=date(2026, 12, 1),
            steam_app_id=12345,
            epic_namespace="fn",
            gog_id="gog_abc",
            cover_url="https://example.com/cover.jpg",
            banner_url="https://example.com/banner.jpg",
            metacritic_score=85,
            steam_review_score=92.5,
            steam_review_count=10000,
            provider_name="steam_community",
            provider_url="https://example.com/game",
            is_free=True,
            free_until=date(2026, 12, 31),
            media=[MediaAsset(type="screenshot", url="https://example.com/ss.png")],
        )
        steam_id = 12345
        meta_score = 85
        review_score = 92.5
        assert game.genres == ["RPG", "Action"]
        assert game.steam_app_id == steam_id
        assert game.metacritic_score == meta_score
        assert game.steam_review_score == review_score
        assert game.is_free is True

    @pytest.mark.unit
    def test_metacritic_score_bounds(self) -> None:
        """Game should reject out-of-range metacritic scores."""
        Game(id="3", title="Edge", provider_name="test", metacritic_score=0)
        Game(id="4", title="Edge", provider_name="test", metacritic_score=100)
        with pytest.raises(ValidationError):
            Game(id="5", title="Over", provider_name="test", metacritic_score=101)
        with pytest.raises(ValidationError):
            Game(id="6", title="Under", provider_name="test", metacritic_score=-1)

    @pytest.mark.unit
    def test_json_roundtrip(self) -> None:
        """Game should survive JSON serialization roundtrip."""
        game = Game(
            id="7",
            title="Roundtrip",
            provider_name="cheapshark",
            genres=["RPG", "Strategy"],
            is_free=True,
        )
        data = game.model_dump_json()
        restored = Game.model_validate_json(data)
        assert restored == game
        assert restored.genres == ["RPG", "Strategy"]

    @pytest.mark.unit
    def test_raw_metadata_preservation(self) -> None:
        """Game should preserve raw_metadata through serialization."""
        metadata = {"foo": "bar", "nested": {"a": 1, "b": [2, 3]}}
        game = Game(id="8", title="Meta", provider_name="test", raw_metadata=metadata)
        assert game.raw_metadata["foo"] == "bar"
        assert game.raw_metadata["nested"]["a"] == 1
        data = game.model_dump_json()
        restored = Game.model_validate_json(data)
        assert restored.raw_metadata == metadata

    @pytest.mark.unit
    def test_missing_id_raises(self) -> None:
        """Game should raise ValidationError when id is missing."""
        with pytest.raises(ValidationError):
            Game(title="No ID", provider_name="test")  # type: ignore[call-arg]

    @pytest.mark.unit
    def test_missing_title_raises(self) -> None:
        """Game should raise ValidationError when title is missing."""
        with pytest.raises(ValidationError):
            Game(id="9", provider_name="test")  # type: ignore[call-arg]

    @pytest.mark.unit
    def test_missing_provider_name_raises(self) -> None:
        """Game should raise ValidationError when provider_name is missing."""
        with pytest.raises(ValidationError):
            Game(id="10", title="No Provider")  # type: ignore[call-arg]
