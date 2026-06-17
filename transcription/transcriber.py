import io
import logging
from abc import ABC, abstractmethod
from functools import lru_cache
from typing import TYPE_CHECKING

from fastapi.concurrency import run_in_threadpool

from transcription.models import Transcript, TranscriptionFailedError

if TYPE_CHECKING:
    from faster_whisper import WhisperModel

logger = logging.getLogger(__name__)


class Transcriber(ABC):
    """Transcribes raw audio bytes into a ``Transcript``."""

    @abstractmethod
    async def transcribe(self, *, data: bytes, filename: str, language: str) -> Transcript: ...


@lru_cache(maxsize=4)
def _load_model(model_size: str, device: str, compute_type: str) -> "WhisperModel":
    # Imported lazily so the (heavy) dependency and model load only happen on first use.
    from faster_whisper import WhisperModel

    logger.info(
        "loading whisper model",
        extra={"model": model_size, "device": device, "compute_type": compute_type},
    )
    return WhisperModel(model_size, device=device, compute_type=compute_type)


class LocalWhisperTranscriber(Transcriber):
    """Whisper transcription running locally via faster-whisper (no API key)."""

    def __init__(self, *, model_size: str, device: str, compute_type: str) -> None:
        self._model_size = model_size
        self._device = device
        self._compute_type = compute_type

    def _transcribe_sync(self, data: bytes, language: str) -> Transcript:
        model = _load_model(self._model_size, self._device, self._compute_type)
        segments, info = model.transcribe(io.BytesIO(data), language=language)
        text = "".join(segment.text for segment in segments).strip()
        detected = getattr(info, "language", None) or language
        return Transcript(text=text, language=detected)

    async def transcribe(self, *, data: bytes, filename: str, language: str) -> Transcript:
        try:
            return await run_in_threadpool(self._transcribe_sync, data, language)
        except Exception as exc:
            logger.error("whisper transcription failed", exc_info=exc)
            raise TranscriptionFailedError("transcription failed") from exc
