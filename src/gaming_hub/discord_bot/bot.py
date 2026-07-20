"""Discord bot lifecycle manager.

Implements ``GamingHubBot`` — the single entry point for all Discord
interactions. It manages the gateway connection, cog auto-discovery, and
global error handling for slash commands.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

import discord
from discord.ext import commands

from gaming_hub.discord_bot.container import ServiceContainer

if TYPE_CHECKING:
    from gaming_hub.config.models import Settings

logger = logging.getLogger(__name__)


class GamingHubBot(commands.Bot):
    """Discord gateway client for the Gaming Hub.

    A ``commands.Bot`` subclass that wires up connection lifecycle events,
    auto-discovers cogs, and provides centralized slash-command error
    handling. Initialize from ``Settings`` and start with ``bot.run()``.
    """

    def __init__(self, settings: Settings) -> None:
        """Initialize the bot from application settings.

        Args:
            settings: Application settings with ``DISCORD_TOKEN`` and
                ``DISCORD_GUILD_IDS``.
        """
        intents = discord.Intents.default()
        intents.message_content = False  # Only slash commands
        intents.guilds = True

        super().__init__(
            command_prefix=commands.when_mentioned_or("/"),
            intents=intents,
            description="Gaming Deals & Automation Hub",
        )
        self._settings = settings
        self._discord_token = settings.discord_token
        self._guild_ids = settings.discord_guild_ids  # list[int] for guild commands
        self._container = ServiceContainer(settings)

    async def on_ready(self) -> None:
        """Handle successful connection: log status and set presence."""
        user = self.user
        assert user is not None  # on_ready only fires once the bot is logged in
        logger.info(f"Logged in as {user} (ID: {user.id})")
        logger.info(f"Connected to {len(self.guilds)} guilds")
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="for /help",
            )
        )

    async def on_disconnect(self) -> None:
        """Log gateway disconnection (discord.py auto-reconnects)."""
        logger.warning("Disconnected from Discord gateway. Reconnecting...")

    async def on_resumed(self) -> None:
        """Log successful session resume after a disconnect."""
        logger.info("Resumed Discord gateway session.")

    async def load_cogs(self) -> None:
        """Auto-discover and load all cogs from the cogs directory and subdirectories."""
        cogs_dir = Path(__file__).parent / "cogs"
        for path in sorted(cogs_dir.rglob("*_cog.py")):
            relative_path = path.relative_to(cogs_dir)
            module_path = relative_path.with_suffix("").as_posix().replace("/", ".")
            cog_name = path.stem
            try:
                await self.load_extension(f"gaming_hub.discord_bot.cogs.{module_path}")
                logger.info(f"Loaded cog: {cog_name}")
            except Exception as e:
                logger.error(f"Failed to load cog {cog_name}: {e}")

    async def on_app_command_error(
        self,
        interaction: discord.Interaction,
        error: discord.app_commands.AppCommandError,
    ) -> None:
        """Global error handler for slash commands.

        Maps known error types to friendly ephemeral messages and logs
        unexpected errors without crashing the gateway connection.
        """
        try:
            if isinstance(error, discord.app_commands.MissingPermissions):
                await interaction.response.send_message(
                    "You don't have permission to use this command.", ephemeral=True,
                )
            elif isinstance(error, discord.app_commands.CommandOnCooldown):
                await interaction.response.send_message(
                    f"Command on cooldown. Try again in {error.retry_after:.0f}s.",
                    ephemeral=True,
                )
            elif isinstance(error, discord.app_commands.BotMissingPermissions):
                await interaction.response.send_message(
                    "I don't have the required permissions to do that.", ephemeral=True,
                )
            else:
                logger.exception(f"Unhandled error in command: {error}")
                await interaction.response.send_message(
                    "An unexpected error occurred. Please try again later.",
                    ephemeral=True,
                )
        except discord.errors.InteractionResponded:
            if isinstance(error, discord.app_commands.MissingPermissions):
                await interaction.followup.send(
                    "You don't have permission to use this command.", ephemeral=True,
                )
            elif isinstance(error, discord.app_commands.CommandOnCooldown):
                await interaction.followup.send(
                    f"Command on cooldown. Try again in {error.retry_after:.0f}s.",
                    ephemeral=True,
                )
            elif isinstance(error, discord.app_commands.BotMissingPermissions):
                await interaction.followup.send(
                    "I don't have the required permissions to do that.", ephemeral=True,
                )
            else:
                logger.exception(f"Unhandled error in command: {error}")
                await interaction.followup.send(
                    "An unexpected error occurred. Please try again later.",
                    ephemeral=True,
                )

    async def setup_hook(self) -> None:
        """Load cogs, initialize posters and scheduler, sync commands."""
        logger.info("Loading cogs...")
        await self.load_cogs()
        logger.info(f"Commands before sync: {len(self.tree.get_commands())}")

        logger.info("Initializing automatic posters...")
        self._poster_registry = self._init_posters()

        logger.info("Running channel startup scheduler...")
        await self._run_channel_scheduler()

        logger.info("Initializing job scheduler...")
        self._job_scheduler = self._init_scheduler()

        if self._settings.enable_google_calendar and self._settings.google_sync_on_startup:
            logger.info("Starting Google Calendar sync on startup...")
            try:
                from gaming_hub.services.calendar_service import CalendarService  # noqa: PLC0415
                calendar = self._container.resolve(CalendarService)
                sync_report = await calendar.sync()
                logger.info(
                    "Startup Calendar Sync: created=%d updated=%d deleted=%d errors=%d",
                    sync_report.created,
                    sync_report.updated,
                    sync_report.deleted,
                    len(sync_report.errors),
                )
            except Exception as exc:
                logger.warning("Startup Calendar Sync failed (non-fatal): %s", exc)

        logger.info("Initializing web API...")
        self._init_api()

        logger.info("Synchronizing application commands...")
        if self._guild_ids:
            for guild_id in self._guild_ids:
                self.tree.copy_global_to(guild=discord.Object(id=guild_id))
            for guild_id in self._guild_ids:
                await self.tree.sync(guild=discord.Object(id=guild_id))
                logger.info(f"Successfully synchronized commands to guild {guild_id}")
        else:
            await self.tree.sync()
        logger.info(f"Successfully synchronized {len(self.tree.get_commands())} slash commands")

    def _init_posters(self) -> Any:
        """Create and return the poster registry."""
        from gaming_hub.discord_bot.posters.factory import create_poster_registry  # noqa: PLC0415
        return create_poster_registry(self, self._settings)

    async def _run_channel_scheduler(self) -> None:
        """Evaluate all poster channels and publish any that are overdue."""
        from gaming_hub.discord_bot.scheduler.channel_scheduler import (
            ChannelScheduler,
            PublicationRepository,
        )
        from gaming_hub.discord_bot.scheduler.force_refresh import (
            force_refresh_monthly,
        )

        # One-time force refresh: when MONTHLY_FORCE_REFRESH=true, replace
        # existing July 2026 monthly messages with newly corrected content.
        await force_refresh_monthly(self, self._settings, self._poster_registry)

        # One-time migration: invalidate old July 2026 monthly records so
        # the new logic regenerates them on this startup.
        repo = PublicationRepository(self._settings.database_dir)
        await repo.init()
        await repo.run_monthly_migration()

        scheduler = ChannelScheduler(
            bot=self,
            settings=self._settings,
            poster_registry=self._poster_registry,
        )
        await scheduler.run()

    def _init_scheduler(self) -> Any:
        """Create and return the JobScheduler (calendar only)."""
        from gaming_hub.automation.scheduler import JobScheduler  # noqa: PLC0415
        from gaming_hub.services.calendar_service import CalendarService  # noqa: PLC0415

        calendar: Any = None
        try:
            calendar = self._container.resolve(CalendarService)
        except KeyError:
            logger.info("CalendarService not registered — calendar jobs will return errors")

        return JobScheduler(
            calendar_service=calendar,
        )

    def _init_api(self) -> None:
        """Start the internal FastAPI server with the scheduler configured."""
        import threading  # noqa: PLC0415

        import uvicorn  # noqa: PLC0415

        from gaming_hub.api.app import create_app  # noqa: PLC0415

        app = create_app(scheduler=self._job_scheduler, settings_override=self._settings)
        port = self._settings.api_port
        thread = threading.Thread(
            target=uvicorn.run,
            args=(app,),
            kwargs={"host": self._settings.api_host, "port": port, "log_level": "info"},
            daemon=True,
        )
        thread.start()
        logger.info("Web API started on %s:%s", self._settings.api_host, port)
