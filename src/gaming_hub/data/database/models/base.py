"""SQLAlchemy declarative base.

All ORM models inherit from this base. Keeps imports centralized for Alembic
and the database bootstrap layer.
"""

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Declarative base for the application ORM."""
