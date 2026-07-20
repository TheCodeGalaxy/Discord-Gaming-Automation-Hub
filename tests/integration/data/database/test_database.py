"""Integration tests for database connection and ORM models."""

from __future__ import annotations

import tempfile
from datetime import UTC, datetime
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from gaming_hub.core.enums import EventType
from gaming_hub.data.database import Database, SqlUnitOfWork
from gaming_hub.data.database.models import (
    AutomationLogModel,
    Base,
    GameModel,
    SaleModel,
    UserPreferencesModel,
)

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture()
def engine():
    """Create an in-memory engine with all tables."""
    return create_async_engine(TEST_DB_URL, echo=False)


@pytest_asyncio.fixture()
async def tables(engine):
    """Create all tables in the in-memory database."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture()
def session_factory(engine):
    """Return an async_sessionmaker bound to the test engine."""
    return async_sessionmaker(engine, class_=AsyncSession)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_wal_mode() -> None:
    """Test that Database.connect() enables WAL journal mode.

    Uses a temporary file because in-memory SQLite does not support WAL.
    """
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name
    try:
        db = Database()
        db.settings.database_url = f"sqlite+aiosqlite:///{db_path}"
        engine = await db.connect()
        async with engine.connect() as conn:
            result = await conn.execute(text("PRAGMA journal_mode"))
            row = result.fetchone()
            assert row[0] == "wal"
        await db.disconnect()
    finally:
        p = Path(db_path)
        if p.exists():
            p.unlink()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_database_disconnect() -> None:
    """Test that Database.disconnect() disposes the engine."""
    db = Database()
    db.settings.database_url = TEST_DB_URL
    engine = await db.connect()
    assert engine is not None
    await db.disconnect()
    # Calling disconnect again should be safe (no-op)
    await db.disconnect()
    # engine property raises RuntimeError after disconnect
    with pytest.raises(RuntimeError, match="Database not connected"):
        _ = db.engine


@pytest.mark.asyncio
@pytest.mark.integration
async def test_create_all_tables() -> None:
    """Test that all ORM models create their tables."""
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with engine.connect() as conn:
        result = await conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"),
        )
        tables = [row[0] for row in result.fetchall()]
    assert "games" in tables
    assert "deals" in tables
    assert "sales" in tables
    assert "user_preferences" in tables
    assert "automation_log" in tables
    await engine.dispose()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_game_crud(tables, session_factory) -> None:
    """Test GameModel insert, select, update, delete."""
    game = GameModel(
        id="test-1",
        title="Test Game",
        provider_name="cheapshark",
        genres=["RPG", "Action"],
        metacritic_score=85,
    )
    async with session_factory() as session:
        session.add(game)
        await session.commit()

    async with session_factory() as session:
        loaded = await session.get(GameModel, "test-1")
        assert loaded is not None
        assert loaded.title == "Test Game"
        assert loaded.genres == ["RPG", "Action"]
        assert loaded.metacritic_score == 85  # noqa: PLR2004

    async with session_factory() as session:
        loaded = await session.get(GameModel, "test-1")
        loaded.metacritic_score = 90
        await session.commit()

    async with session_factory() as session:
        loaded = await session.get(GameModel, "test-1")
        assert loaded.metacritic_score == 90  # noqa: PLR2004

    async with session_factory() as session:
        loaded = await session.get(GameModel, "test-1")
        await session.delete(loaded)
        await session.commit()

    async with session_factory() as session:
        loaded = await session.get(GameModel, "test-1")
        assert loaded is None


@pytest.mark.asyncio
@pytest.mark.integration
async def test_sql_unit_of_work_commit(tables, session_factory) -> None:
    """Test SqlUnitOfWork commits data on success."""
    async with SqlUnitOfWork(session_factory) as uow:
        game = GameModel(id="uow-1", title="UoW Commit", provider_name="test")
        uow.session.add(game)
        await uow.commit()

    async with session_factory() as session:
        loaded = await session.get(GameModel, "uow-1")
        assert loaded is not None


@pytest.mark.asyncio
@pytest.mark.integration
async def test_sql_unit_of_work_rollback_on_uncommitted(tables, session_factory) -> None:
    """Test SqlUnitOfWork rolls back uncommitted data on exception."""
    try:
        async with SqlUnitOfWork(session_factory) as uow:
            game = GameModel(id="uow-3", title="UoW Uncommitted", provider_name="test")
            uow.session.add(game)
            msg = "Simulated failure before commit"
            raise RuntimeError(msg)
    except RuntimeError:
        pass

    async with session_factory() as session:
        loaded = await session.get(GameModel, "uow-3")
        assert loaded is None


@pytest.mark.asyncio
@pytest.mark.integration
async def test_user_preferences_crud(tables, session_factory) -> None:
    """Test UserPreferencesModel insert and update."""
    prefs = UserPreferencesModel(
        discord_user_id=12345,
        favorite_genres=["RPG", "Strategy"],
        discount_threshold=80,
    )
    async with session_factory() as session:
        session.add(prefs)
        await session.commit()

    async with session_factory() as session:
        loaded = await session.get(UserPreferencesModel, 12345)
        assert loaded is not None
        assert loaded.favorite_genres == ["RPG", "Strategy"]
        assert loaded.discount_threshold == 80  # noqa: PLR2004


@pytest.mark.asyncio
@pytest.mark.integration
async def test_automation_log_insert(tables, session_factory) -> None:
    """Test AutomationLogModel insert and select."""
    log_entry = AutomationLogModel(
        job_name="daily_free_games",
        channel_id=98765,
        triggered_at=datetime.now(UTC).replace(tzinfo=None),
        status="completed",
        result_count=5,
    )
    async with session_factory() as session:
        session.add(log_entry)
        await session.commit()

    async with session_factory() as session:
        result = await session.execute(
            select(AutomationLogModel).where(AutomationLogModel.job_name == "daily_free_games"),
        )
        loaded = result.scalar_one()
        assert loaded.status == "completed"
        assert loaded.result_count == 5  # noqa: PLR2004


@pytest.mark.asyncio
@pytest.mark.integration
async def test_sale_model(tables, engine) -> None:
    """Test SaleModel insert and query."""
    async with AsyncSession(engine) as session:
        sale = SaleModel(
            id="sale-1",
            title="Summer Sale",
            event_type=str(EventType.SteamSale),
            store="steam",
            starts_at=datetime(2026, 7, 1, 0, 0, 0),
            ends_at=datetime(2026, 7, 31, 23, 59, 59),
            reminder_minutes=60,
        )
        session.add(sale)
        await session.commit()

    async with AsyncSession(engine) as session:
        loaded = await session.get(SaleModel, "sale-1")
        assert loaded is not None
        assert loaded.event_type == "steam_sale"
        assert loaded.reminder_minutes == 60  # noqa: PLR2004
