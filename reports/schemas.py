from typing import Self

from pydantic import BaseModel

from reports.models import ReportStatus, StoredReport


class NextMeetingReportResponse(BaseModel):
    patient_id: str
    meeting_id: str
    status: ReportStatus
    intro: str | None = None
    changes: list[str] | None = None
    open_topics: list[str] | None = None
    source_meeting_ids: list[str] | None = None
    last_summary_excerpt: str | None = None
    generated_at: str | None = None
    model: str | None = None
    error: str | None = None

    @classmethod
    def from_report(
        cls,
        report: StoredReport,
        *,
        last_summary_excerpt: str | None = None,
    ) -> Self:
        return cls(
            patient_id=str(report.patient_id),
            meeting_id=str(report.meeting_id),
            status=report.status,
            intro=report.intro,
            changes=list(report.changes) if report.changes is not None else [],
            open_topics=list(report.open_topics) if report.open_topics is not None else [],
            source_meeting_ids=[str(mid) for mid in report.source_meeting_ids],
            last_summary_excerpt=last_summary_excerpt,
            generated_at=(report.updated_at.isoformat() if report.updated_at else None),
            model=report.model or None,
            error=report.error,
        )


class MeetingReportListItem(BaseModel):
    meeting_id: str
    status: ReportStatus
    generated_at: str | None = None

    @classmethod
    def from_report(cls, report: StoredReport) -> Self:
        return cls(
            meeting_id=str(report.meeting_id),
            status=report.status,
            generated_at=(report.updated_at.isoformat() if report.updated_at else None),
        )
