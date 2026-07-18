from dataclasses import dataclass
from typing import Literal

AudioFormat = Literal["mp3", "mp3_fast", "wav"]
MIN_SPEECH_SPEED = 0.7
MAX_SPEECH_SPEED = 1.2
SUPPORTED_AUDIO_FORMATS: tuple[AudioFormat, ...] = ("mp3", "mp3_fast", "wav")


@dataclass(frozen=True)
class SynthesizedAudio:
    """Audio produced from text and the metadata needed to serve it."""

    data: bytes
    media_type: str
    file_extension: str
