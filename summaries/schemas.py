from typing import Self

from pydantic import BaseModel

from summaries.format import normalize_summary_output
from summaries.models import StoredSummary, SummaryStatus


class SummaryResponse(BaseModel):
    meeting_id: str
    status: SummaryStatus
    text: str | None = None
    model: str | None = None
    error: str | None = None

    @classmethod
    def from_summary(cls, summary: StoredSummary) -> Self:
        text = summary.text
        # Rows saved before normalize (or partial JSON) still arrive as JSON —
        # convert on read so clients always get Hebrew sections when possible.
        if text and summary.status == "ready":
            text = normalize_summary_output(text)
        return cls(
            meeting_id=str(summary.meeting_id),
            status=summary.status,
            text=text,
            model=summary.model or None,
            error=summary.error,
        )
