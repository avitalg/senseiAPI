import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKeyConstraint, String, Text, UniqueConstraint, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class TranscriptRecord(Base):
    """Persisted transcript for a therapy meeting."""

    __tablename__ = "transcripts"
    __table_args__ = (
        ForeignKeyConstraint(
            ["user_id", "meeting_id"],
            ["calendar_events.user_id", "calendar_events.id"],
            ondelete="CASCADE",
        ),
        UniqueConstraint("user_id", "meeting_id", name="uq_transcripts_user_meeting"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    # meeting_id references calendar_events.id (same entity as API meeting_id).
    meeting_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        index=True,
    )
    raw_text: Mapped[str] = mapped_column(Text)
    diarized_segments: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    language: Mapped[str] = mapped_column(String(16), default="he", server_default="he")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
