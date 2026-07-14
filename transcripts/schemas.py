from typing import Self

from pydantic import BaseModel

from transcripts.models import StoredTranscript

_EXCERPT_MAX = 200


class TranscriptExistsResponse(BaseModel):
    meeting_id: str
    transcript_id: str
    excerpt: str | None = None

    @classmethod
    def from_transcript(cls, transcript: StoredTranscript) -> Self:
        text = transcript.raw_text.strip()
        excerpt = None
        if text:
            excerpt = text if len(text) <= _EXCERPT_MAX else text[: _EXCERPT_MAX - 1].rstrip() + "…"
        return cls(
            meeting_id=str(transcript.meeting_id),
            transcript_id=str(transcript.id),
            excerpt=excerpt,
        )
