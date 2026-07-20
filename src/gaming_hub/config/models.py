"""Pydantic settings models.

Every application behavior tunable through the environment is declared here.
Defaults are safe for local development and Docker Compose.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Root application settings.

    Attributes match the variables documented in ``.env.example``. Values are
    parsed from environment variables and ``.env`` files.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        validate_default=True,
    )

    # -------------------------------------------------------------------------
    # Core application
    # -------------------------------------------------------------------------
    app_name: str = Field(default="GamingHub", description="Application display name.")
    environment: str = Field(default="development", description="Runtime environment.")
    debug: bool = Field(default=False, description="Enable debug mode verbose output.")
    secret_key: str = Field(default="change-me-in-production", description="Internal signing key.")
    test_mode: bool = Field(default=False, description="Publish every channel once on startup.")
    monthly_force_refresh: bool = Field(
        default=False,
        description="One-time force-refresh July 2026 monthly posts with corrected collectors.",
    )

    # -------------------------------------------------------------------------
    # Discord
    # -------------------------------------------------------------------------
    discord_token: str = Field(default="", description="Discord bot token.")
    discord_guild_id: int | None = Field(default=None, description="Target guild ID for commands.")
    discord_guild_ids: list[int] = Field(
        default_factory=list, description="Guild IDs for instant slash command registration.",
    )
    discord_prefix: str = Field(default="!gh", description="Legacy prefix (optional).")
    discord_default_channel_id: int | None = Field(default=None, description="Fallback channel ID.")
    discord_free_games_channel_id: int | None = Field(default=None)
    discord_crazy_discounts_channel_id: int | None = Field(default=None)
    discord_top_games_channel_id: int | None = Field(default=None)
    discord_major_updates_channel_id: int | None = Field(default=None)
    discord_coming_soon_channel_id: int | None = Field(default=None)
    discord_admin_ids: list[int] = Field(default_factory=list)

    # -------------------------------------------------------------------------
    # Gaming preferences
    # -------------------------------------------------------------------------
    favorite_genres: list[str] = Field(default_factory=lambda: ["RPG", "Action", "Indie"])
    crazy_discount_threshold: int = Field(default=80, ge=0, le=100)
    new_release_days: int = Field(default=7, ge=1)
    default_page_size: int = Field(default=10, ge=1, le=100)
    max_page_size: int = Field(default=50, ge=1, le=200)
    surprise_history_size: int = Field(default=50, ge=1)
    upcoming_days_ahead: int = Field(default=30, ge=1)

    # -------------------------------------------------------------------------
    # Providers
    # -------------------------------------------------------------------------
    cheapshark_base_url: str = Field(default="https://www.cheapshark.com/api/1.0")
    epic_base_url: str = Field(default="https://store-site-backend-static.ak.epicgames.com")
    epic_graphql_url: str = Field(default="https://graphql.epicgames.com/graphql")
    steam_community_base_url: str = Field(default="https://steamcommunity.com")
    steam_store_base_url: str = Field(default="https://store.steampowered.com")
    isthereanydeal_base_url: str = Field(default="https://api.isthereanydeal.com")
    isthereanydeal_api_key: str | None = Field(default=None)
    rawg_base_url: str = Field(default="https://api.rawg.io/api")
    rawg_api_key: str | None = Field(default=None)

    # -------------------------------------------------------------------------
    # HTTP & cache
    # -------------------------------------------------------------------------
    http_timeout: int = Field(default=30, ge=1)
    http_max_retries: int = Field(default=3, ge=0)
    cache_backend: str = Field(default="memory")
    cache_ttl_seconds: int = Field(default=300, ge=0)

    # -------------------------------------------------------------------------
    # Database
    # -------------------------------------------------------------------------
    database_url: str = Field(default="sqlite+aiosqlite:///data/gaming_hub.db")
    database_echo: bool = Field(default=False)

    @property
    def database_dir(self) -> str:
        """Return the directory containing the SQLite database file."""
        if self.database_url.startswith("sqlite"):
            path = self.database_url.split("///", 1)[1] if "///" in self.database_url else "data/gaming_hub.db"
            return str(Path(path).parent)
        return "data"

    # -------------------------------------------------------------------------
    # API
    # -------------------------------------------------------------------------
    api_host: str = Field(default="0.0.0.0")
    api_port: int = Field(default=8000, ge=1, le=65535)
    api_trusted_hosts: list[str] = Field(
        default_factory=lambda: ["127.0.0.1", "::1", "172.0.0.0/8"]
    )

    # -------------------------------------------------------------------------
    # Automation / n8n
    # -------------------------------------------------------------------------
    automation_enabled: bool = Field(default=True)
    n8n_webhook_prefix: str = Field(default="/webhooks/n8n")
    n8n_webhook_secret: str = Field(default="")

    # -------------------------------------------------------------------------
    # Google Calendar
    # -------------------------------------------------------------------------
    google_calendar_credentials_path: str | None = Field(default=None)
    google_service_account_json: str | None = Field(default=None)
    google_calendar_id: str = Field(default="primary")
    google_calendar_default_reminder_minutes: int = Field(default=60, ge=0)
    enable_google_calendar: bool = Field(default=False)
    google_sync_years_ahead: int = Field(default=1, ge=0)
    google_sync_on_startup: bool = Field(default=False, description="Full sync when bot starts.")
    google_delete_old_events: bool = Field(default=False, description="Remove past events on sync.")
    google_event_color_releases: int = Field(default=9, ge=1, le=11, description="Calendar color ID for game-release events.")
    google_event_color_updates: int = Field(default=10, ge=1, le=11, description="Calendar color ID for major-update events.")

    # -------------------------------------------------------------------------
    # Logging
    # -------------------------------------------------------------------------
    log_level: str = Field(default="INFO")
    log_json: bool = Field(default=False)
    log_file_path: str | None = Field(default=None)
    log_rotation: bool = Field(default=False)

    # Free games
    free_games_expiry_hours: int = Field(
        default=48, ge=1,
        description="Hours before free_until to flag as expiring soon.",
    )

    @field_validator("favorite_genres", "api_trusted_hosts", "discord_admin_ids", mode="before")
    @classmethod
    def _split_comma_separated(cls, value: str | list[str]) -> list[str]:
        """Parse comma-separated strings into lists."""
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        if isinstance(value, list):
            return value
        raise TypeError(f"Expected str or list, got {type(value).__name__}")

    @field_validator("environment")
    @classmethod
    def _normalize_environment(cls, value: str) -> str:
        """Normalize environment string for predictable branching."""
        return value.strip().lower()

    @property
    def is_production(self) -> bool:
        """Return True when running in production mode."""
        return self.environment == "production"

    @property
    def is_development(self) -> bool:
        """Return True when running in development mode."""
        return self.environment == "development"
