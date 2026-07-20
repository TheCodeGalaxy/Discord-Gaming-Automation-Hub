"""Unit tests for GamingHubBot."""
# ruff: noqa: PLR2004 — test assertions use literal magic values for clarity

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import discord
import pytest

from gaming_hub.config.models import Settings
from gaming_hub.discord_bot import bot as bot_module
from gaming_hub.discord_bot.bot import GamingHubBot

COGS_DIR = Path(bot_module.__file__).parent / "cogs"


@pytest.fixture()
def settings() -> Settings:
    """Return a settings object with a dummy Discord token."""
    settings = Settings(_env_file=None)
    settings.discord_token = "TEST_TOKEN"
    settings.discord_guild_ids = [111222333444]
    return settings


@pytest.fixture()
def bot(settings: Settings) -> GamingHubBot:
    """Return a GamingHubBot with the Bot base class __init__ mocked."""
    with patch("discord.ext.commands.Bot.__init__", return_value=None):
        instance = GamingHubBot(settings)
    return instance


@pytest.mark.unit
class TestGamingHubBotInit:
    """Initialization and configuration wiring."""

    def test_init_stores_settings_and_token(self, settings: Settings) -> None:
        """Bot stores settings, token, and guild ids."""
        with patch("discord.ext.commands.Bot.__init__", return_value=None):
            instance = GamingHubBot(settings)
        assert instance._settings is settings
        assert instance._discord_token == "TEST_TOKEN"
        assert instance._guild_ids == [111222333444]

    def test_init_calls_bot_superclass(self, settings: Settings) -> None:
        """Initialization forwards to commands.Bot with slash-only intents."""
        with patch("discord.ext.commands.Bot.__init__") as mock_super:
            GamingHubBot(settings)
        mock_super.assert_called_once()
        _, kwargs = mock_super.call_args
        assert kwargs["command_prefix"] is not None
        assert kwargs["description"] == "Gaming Deals & Automation Hub"
        intents = kwargs["intents"]
        assert intents.guilds is True
        assert intents.message_content is False


@pytest.mark.unit
class TestGamingHubBotLoadCogs:
    """Cog auto-discovery."""

    @pytest.mark.asyncio
    async def test_load_cogs_calls_load_extension_per_cog(self, bot: GamingHubBot) -> None:
        """Each *_cog.py file is loaded via load_extension."""
        existing = sorted(COGS_DIR.rglob("*_cog.py"))
        load_extension = AsyncMock()
        with patch.object(bot, "load_extension", load_extension):
            await bot.load_cogs()
        if existing:
            assert load_extension.call_count == len(existing)
        else:
            load_extension.assert_not_called()

    @pytest.mark.asyncio
    async def test_load_cogs_logs_failure_and_continues(self, bot: GamingHubBot) -> None:
        """A failing cog load is logged and does not raise."""
        temp_cog = COGS_DIR / "_load_cogs_failure_cog.py"
        temp_cog.write_text("# temporary failing cog\n")
        load_extension = AsyncMock(side_effect=Exception("boom"))
        try:
            with (
                patch.object(bot, "load_extension", load_extension),
                patch("gaming_hub.discord_bot.bot.logger") as mock_logger,
            ):
                await bot.load_cogs()
            mock_logger.error.assert_called()
        finally:
            temp_cog.unlink(missing_ok=True)


@pytest.mark.unit
class TestGamingHubBotErrorHandler:
    """Global slash-command error handling."""

    @pytest.mark.asyncio
    async def test_missing_permissions_respond_ephemeral(self, bot: GamingHubBot) -> None:
        """MissingPermissions maps to a permission error message."""
        interaction = MagicMock()
        interaction.response = MagicMock()
        interaction.response.send_message = AsyncMock()
        error = discord.app_commands.MissingPermissions([])
        await bot.on_app_command_error(interaction, error)
        interaction.response.send_message.assert_called_once_with(
            "You don't have permission to use this command.", ephemeral=True,
        )

    @pytest.mark.asyncio
    async def test_command_on_cooldown_respond_retry(self, bot: GamingHubBot) -> None:
        """CommandOnCooldown includes the retry delay."""
        interaction = MagicMock()
        interaction.response = MagicMock()
        interaction.response.send_message = AsyncMock()
        error = discord.app_commands.CommandOnCooldown(MagicMock(), 42.0)
        await bot.on_app_command_error(interaction, error)
        args, kwargs = interaction.response.send_message.call_args
        assert "42s" in args[0]
        assert kwargs["ephemeral"] is True

    @pytest.mark.asyncio
    async def test_bot_missing_permissions_respond_message(self, bot: GamingHubBot) -> None:
        """BotMissingPermissions maps to a bot-permission message."""
        interaction = MagicMock()
        interaction.response = MagicMock()
        interaction.response.send_message = AsyncMock()
        error = discord.app_commands.BotMissingPermissions([])
        await bot.on_app_command_error(interaction, error)
        interaction.response.send_message.assert_called_once_with(
            "I don't have the required permissions to do that.", ephemeral=True,
        )

    @pytest.mark.asyncio
    async def test_unexpected_error_respond_generic_and_log(self, bot: GamingHubBot) -> None:
        """Unhandled errors return a generic message and are logged."""
        interaction = MagicMock()
        interaction.response = MagicMock()
        interaction.response.send_message = AsyncMock()
        with patch("gaming_hub.discord_bot.bot.logger") as mock_logger:
            await bot.on_app_command_error(interaction, RuntimeError("kaboom"))
        interaction.response.send_message.assert_called_once_with(
            "An unexpected error occurred. Please try again later.", ephemeral=True,
        )
        mock_logger.exception.assert_called_once()


@pytest.mark.unit
class TestGamingHubBotLifecycle:
    """Connection lifecycle events."""

    @pytest.mark.asyncio
    async def test_on_ready_sets_watching_presence(self, bot: GamingHubBot) -> None:
        """on_ready logs the user and sets a watching presence."""
        user = MagicMock()
        user.id = 987654321
        bot.change_presence = AsyncMock()

        with (
            patch.object(type(bot), "user", new=PropertyMock(return_value=user)),
            patch.object(
                type(bot),
                "guilds",
                new=PropertyMock(return_value=[MagicMock(), MagicMock()]),
            ),
            patch("gaming_hub.discord_bot.bot.logger") as mock_logger,
        ):
            await bot.on_ready()

        assert mock_logger.info.call_count == 2
        bot.change_presence.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_on_disconnect_logs_warning(self, bot: GamingHubBot) -> None:
        """on_disconnect logs a warning."""
        with patch("gaming_hub.discord_bot.bot.logger") as mock_logger:
            await bot.on_disconnect()
        mock_logger.warning.assert_called_once()

    @pytest.mark.asyncio
    async def test_on_resumed_logs_info(self, bot: GamingHubBot) -> None:
        """on_resumed logs an info message."""
        with patch("gaming_hub.discord_bot.bot.logger") as mock_logger:
            await bot.on_resumed()
        mock_logger.info.assert_called_once()
