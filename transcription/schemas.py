from typing import Self

from pydantic import BaseModel

from transcription.models import Transcript


class TranscriptionResponse(BaseModel):
    id: str
    language: str
    text: str

    @classmethod
    def from_transcript(cls, audio_id: str, transcript: Transcript) -> Self:
        return cls(id=audio_id, language=transcript.language, text=transcript.text)
