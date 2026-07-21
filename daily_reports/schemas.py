import uuid
from datetime import date
from typing import Self

from pydantic import BaseModel

from daily_reports.models import DailyReportStatus, StoredDailyReport

DEFAULT_DAILY_MEETING_LIMIT = 4
MAX_DAILY_MEETING_LIMIT = 20
DEFAULT_DAILY_TIME_ZONE = "Asia/Jerusalem"


class DailyMeetingReportResponse(BaseModel):
    id: uuid.UUID
    report_date: date
    time_zone: str
    status: DailyReportStatus
    meeting_limit: int
    meeting_count: int
    text: str | None = None
    model: str | None = None
    generated_at: str | None = None
    error: str | None = None

    @classmethod
    def from_report(cls, report: StoredDailyReport) -> Self:
        generated_at = None
        if report.status in ("ready", "failed"):
            generated_at = report.updated_at.isoformat()
        return cls(
            id=report.id,
            report_date=report.report_date,
            time_zone=report.time_zone,
            status=report.status,
            meeting_limit=report.meeting_limit,
            meeting_count=report.meeting_count,
            text=report.text,
            model=report.model or None,
            generated_at=generated_at,
            error=report.error,
        )
