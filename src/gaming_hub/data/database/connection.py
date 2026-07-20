"""SQLAlchemy async engine factory and lifecycle."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine

from gaming_hub.config.loader import load_settings


class Database:
    """SQLAlchemy engine and session factory manager.

    Handles engine creation with SQLite WAL mode optimizations, graceful
    shutdown, and programmatic Alembic migration execution.
    """

    def __init__(self) -> None:
        """Read settings and prepare engine placeholder."""
        self.settings = load_settings()
        self._engine: AsyncEngine | None = None

    async def connect(self) -> AsyncEngine:
        """Create and return the async engine with WAL mode enabled.

        Returns:
            Configured AsyncEngine instance.
        """
        kwargs: dict[str, Any] = {"echo": self.settings.database_echo}

        if self.settings.database_url.startswith("sqlite"):
            kwargs["connect_args"] = {
                "check_same_thread": False,
                "timeout": 30,
            }

        self._engine = create_async_engine(
            self.settings.database_url,
            **kwargs,
        )

        async with self._engine.connect() as conn:
            await conn.execute(text("PRAGMA journal_mode=WAL"))
            await conn.execute(text("PRAGMA foreign_keys=ON"))

        return self._engine

    async def disconnect(self) -> None:
        """Dispose the engine and close all connections gracefully."""
        if self._engine is not None:
            await self._engine.dispose()
            self._engine = None

    @property
    def engine(self) -> AsyncEngine:
        """Return the current engine or raise if not connected."""
        if self._engine is None:
            raise RuntimeError("Database not connected. Call connect() first.")
        return self._engine
