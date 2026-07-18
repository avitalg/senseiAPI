from dataclasses import dataclass
from typing import Literal

AudioFormat = Literal["mp3", "wav"]


@dataclass(frozen=True)
class SynthesizedAudio:
    """Audio produced from text and the metadata needed to serve it."""

    data: bytes
    media_type: str
    file_extension: str
