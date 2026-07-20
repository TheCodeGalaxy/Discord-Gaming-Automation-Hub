"""Automation audit log ORM model."""

from __future__ import annotations

from datetime import datetime  # noqa: TC003 — needed at runtime by SQLAlchemy's annotation resolver

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from gaming_hub.data.database.models.base import Base


class AutomationLogModel(Base):
    """Audit trail for scheduled automation jobs."""

    __tablename__ = "automation_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_name: Mapped[str] = mapped_column(String(128), nullable=False)
    channel_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    triggered_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    result_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    def __repr__(self) -> str:
        """Return a developer-friendly string representation."""
        return f"<AutomationLogModel id={self.id} job={self.job_name!r}>"
