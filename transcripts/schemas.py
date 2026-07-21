"""HTTP schemas for meeting transcripts."""

from __future__ import annotations

from pydantic import BaseModel

from transcripts.models import StoredTranscript


class MeetingTranscriptOut(BaseModel):
    meeting_id: str
    transcript_id: str
    excerpt: str | None = None

    @classmethod
    def from_stored(
        cls,
        transcript: StoredTranscript,
        *,
        excerpt_max: int = 240,
    ) -> MeetingTranscriptOut:
        text = (transcript.raw_text or "").strip()
        excerpt: str | None = None
        if text:
            excerpt = text if len(text) <= excerpt_max else text[: excerpt_max - 1].rstrip() + "…"
        return cls(
            meeting_id=str(transcript.meeting_id),
            transcript_id=str(transcript.id),
            excerpt=excerpt,
        )
