import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    DateTime,
    ForeignKeyConstraint,
    Index,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class NextMeetingReportRecord(Base):
    """Prep brief for a specific upcoming/in-progress calendar meeting."""

    __tablename__ = "next_meeting_reports"
    __table_args__ = (
        ForeignKeyConstraint(
            ["user_id", "patient_id"],
            ["patients.user_id", "patients.id"],
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["user_id", "meeting_id"],
            ["calendar_events.user_id", "calendar_events.id"],
            ondelete="CASCADE",
        ),
        UniqueConstraint("user_id", "meeting_id", name="uq_reports_user_meeting"),
        Index("ix_next_meeting_reports_user_patient", "user_id", "patient_id"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    patient_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    # meeting_id references calendar_events.id (prep brief target session).
    meeting_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True)
    status: Mapped[str] = mapped_column(String(16), default="pending", server_default="pending")
    intro: Mapped[str | None] = mapped_column(Text, nullable=True)
    changes: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    open_topics: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    source_meeting_ids: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    model: Mapped[str] = mapped_column(String(64), default="", server_default="")
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
