import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

ReportStatus = Literal["pending", "running", "ready", "failed"]


class ReportFailedError(Exception):
    """Raised when a next-meeting report could not be generated."""


class ReportNotFoundError(Exception):
    """Raised when no report has been requested for the given meeting."""

    def __init__(self, patient_id: uuid.UUID, meeting_id: uuid.UUID) -> None:
        super().__init__(
            f"no meeting report for patient {patient_id!r} meeting {meeting_id!r}",
        )
        self.patient_id = patient_id
        self.meeting_id = meeting_id


class NoUpcomingMeetingError(Exception):
    """Raised when a patient has no in-progress or upcoming calendar meeting."""

    def __init__(self, patient_id: uuid.UUID) -> None:
        super().__init__(f"no upcoming meeting for patient {patient_id!r}")
        self.patient_id = patient_id


class MeetingPatientMismatchError(Exception):
    """Raised when a calendar event does not belong to the requested patient."""

    def __init__(self, patient_id: uuid.UUID, meeting_id: uuid.UUID) -> None:
        super().__init__(
            f"calendar event {meeting_id!r} does not belong to patient {patient_id!r}",
        )
        self.patient_id = patient_id
        self.meeting_id = meeting_id


@dataclass(frozen=True)
class GeneratedReport:
    """Parsed model output for a prep brief."""

    intro: str
    changes: list[str]
    open_topics: list[str]
    model: str
    raw_text: str


@dataclass(frozen=True)
class StoredReport:
    """Persisted meeting prep report row."""

    id: uuid.UUID
    patient_id: uuid.UUID
    meeting_id: uuid.UUID
    status: ReportStatus
    intro: str | None
    changes: list[str]
    open_topics: list[str]
    source_meeting_ids: list[uuid.UUID]
    model: str
    error: str | None
    created_at: datetime
    updated_at: datetime
