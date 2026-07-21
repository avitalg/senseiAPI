import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import Date, DateTime, Integer, String, Text, UniqueConstraint, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class DailyMeetingReportRecord(Base):
    """One current daily brief for a therapist and local calendar date."""

    __tablename__ = "daily_meeting_reports"
    __table_args__ = (
        UniqueConstraint("user_id", "report_date", name="uq_daily_reports_user_date"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    report_date: Mapped[date] = mapped_column(Date)
    # Metadata only: time_zone deliberately does not participate in report identity.
    time_zone: Mapped[str] = mapped_column(String(64), default="Asia/Jerusalem")
    status: Mapped[str] = mapped_column(String(16), default="pending", server_default="pending")
    meeting_limit: Mapped[int] = mapped_column(Integer, default=4, server_default="4")
    meeting_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    text: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_meeting_ids: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    source_report_ids: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    model: Mapped[str] = mapped_column(String(64), default="", server_default="")
    prompt_version: Mapped[str] = mapped_column(String(32), default="", server_default="")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
