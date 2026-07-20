"""SQLAlchemy unit-of-work adapter.

Wraps an async session factory and provides commit/rollback lifecycle
through the UnitOfWork port interface.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from gaming_hub.core.interfaces import UnitOfWork


class SqlUnitOfWork(UnitOfWork):
    """Async SQLAlchemy unit of work.

    Usage::

        async with SqlUnitOfWork(session_factory) as uow:
            uow.session.add(some_model)
            await uow.commit()
    """

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        """Initialize with a session factory."""
        self._session_factory = session_factory
        self.session: AsyncSession | None = None

    async def __aenter__(self) -> UnitOfWork:
        """Enter the async context manager and create a new session."""
        self.session = self._session_factory()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        """Roll back on exception, then close the session."""
        if exc_type is not None:
            await self.rollback()
        if self.session is not None:
            await self.session.close()
            self.session = None

    async def commit(self) -> None:
        """Commit the current transaction."""
        if self.session is not None:
            await self.session.commit()

    async def rollback(self) -> None:
        """Roll back the current transaction."""
        if self.session is not None:
            await self.session.rollback()
