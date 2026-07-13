import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

ReportStatus = Literal["pending", "running", "ready", "failed"]


class ReportFailedError(Exception):
    """Raised when a next-meeting report could not be generated."""


class ReportNotFoundError(Exception):
    """Raised when no report has been requested for the given patient."""

    def __init__(self, patient_id: uuid.UUID) -> None:
        super().__init__(f"no next-meeting report for patient {patient_id!r}")
        self.patient_id = patient_id


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
    """Persisted next-meeting report row."""

    id: uuid.UUID
    patient_id: uuid.UUID
    status: ReportStatus
    intro: str | None
    changes: list[str]
    open_topics: list[str]
    source_meeting_ids: list[uuid.UUID]
    model: str
    error: str | None
    created_at: datetime
    updated_at: datetime
