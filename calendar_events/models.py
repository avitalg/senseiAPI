import uuid
from dataclasses import dataclass
from datetime import datetime


class CalendarEventNotFoundError(Exception):
    """Raised when a requested therapy meeting does not exist."""

    def __init__(self, meeting_id: uuid.UUID) -> None:
        super().__init__(f"meeting {meeting_id!r} not found")
        self.meeting_id = meeting_id

    @property
    def event_id(self) -> uuid.UUID:
        """Deprecated alias — same as meeting_id (calendar_events.id)."""
        return self.meeting_id


@dataclass(frozen=True)
class CalendarEvent:
    id: uuid.UUID
    title: str
    description: str | None
    start_at: datetime
    end_at: datetime
    created_at: datetime
    user_id: uuid.UUID
    patient_id: uuid.UUID | None = None
