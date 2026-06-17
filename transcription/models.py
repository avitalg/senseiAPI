from dataclasses import dataclass


class TranscriptionFailedError(Exception):
    """Raised when transcription fails."""


@dataclass(frozen=True)
class Transcript:
    """The result of transcribing an audio file."""

    text: str
    language: str
