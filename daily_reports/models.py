import uuid
from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal

DailyReportStatus = Literal["pending", "running", "ready", "failed"]


class DailyReportFailedError(Exception):
    """Raised when a daily meeting report could not be generated."""


@dataclass(frozen=True)
class DailyMeetingContext:
    """One scheduled meeting and its prepared clinical context."""

    meeting_id: uuid.UUID
    patient_id: uuid.UUID
    patient_name: str
    start_at: datetime
    intro: str | None
    changes: list[str]
    open_topics: list[str]
    context_available: bool


@dataclass(frozen=True)
class GeneratedDailyReport:
    """Validated model output for a daily therapist brief."""

    text: str
    model: str
    raw_text: str


@dataclass(frozen=True)
class StoredDailyReport:
    """Persisted daily report row."""

    user_id: uuid.UUID
    id: uuid.UUID
    report_date: date
    time_zone: str
    status: DailyReportStatus
    meeting_limit: int
    meeting_count: int
    text: str | None
    source_meeting_ids: list[uuid.UUID]
    source_report_ids: list[uuid.UUID]
    model: str
    prompt_version: str
    error: str | None
    created_at: datetime
    updated_at: datetime
