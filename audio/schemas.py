from typing import Self

from pydantic import BaseModel

from audio.models import SavedAudio, StoredAudioFile
from transcription.models import Transcript


class AudioUploadResponse(BaseModel):
    id: str
    filename: str
    content_type: str
    size_bytes: int
    language: str
    text: str

    @classmethod
    def from_upload(cls, saved: SavedAudio, transcript: Transcript) -> Self:
        return cls(
            id=saved.id,
            filename=saved.filename,
            content_type=saved.content_type,
            size_bytes=saved.size_bytes,
            language=transcript.language,
            text=transcript.text,
        )


class AudioFileInfo(BaseModel):
    id: str
    size_bytes: int

    @classmethod
    def from_stored(cls, stored: StoredAudioFile) -> Self:
        return cls(id=stored.id, size_bytes=stored.size_bytes)
