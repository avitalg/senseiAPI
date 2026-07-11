from typing import Self

from pydantic import BaseModel

from summaries.models import StoredSummary, SummaryStatus


class SummaryResponse(BaseModel):
    meeting_id: str
    status: SummaryStatus
    text: str | None = None
    insights: list[str] = []
    risk_flags: list[str] = []
    model: str | None = None
    error: str | None = None

    @classmethod
    def from_summary(cls, summary: StoredSummary) -> Self:
        return cls(
            meeting_id=str(summary.meeting_id),
            status=summary.status,
            text=summary.text,
            insights=list(summary.insights),
            risk_flags=list(summary.risk_flags),
            model=summary.model or None,
            error=summary.error,
        )
