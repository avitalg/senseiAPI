from dataclasses import dataclass


class UnsupportedAudioTypeError(Exception):
    """Raised when the uploaded file is not an accepted audio type."""

    def __init__(self, content_type: str) -> None:
        super().__init__(f"unsupported audio type: {content_type or 'unknown'}")
        self.content_type = content_type


class EmptyAudioError(Exception):
    """Raised when the uploaded file has no content."""


class AudioTooLargeError(Exception):
    """Raised when the uploaded file exceeds the allowed size."""

    def __init__(self, size_bytes: int, max_bytes: int) -> None:
        super().__init__(f"audio is {size_bytes} bytes; max allowed is {max_bytes}")
        self.size_bytes = size_bytes
        self.max_bytes = max_bytes


class AudioNotFoundError(Exception):
    """Raised when a requested audio file does not exist."""

    def __init__(self, audio_id: str) -> None:
        super().__init__(f"audio {audio_id!r} not found")
        self.audio_id = audio_id


@dataclass(frozen=True)
class SavedAudio:
    id: str
    filename: str
    content_type: str
    size_bytes: int
    data: bytes


@dataclass(frozen=True)
class StoredAudioFile:
    id: str
    size_bytes: int
