import logging
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any, Protocol

from elevenlabs.types import VoiceSettings

from tts.errors import (
    SpeechSynthesisFailedError,
    TTSConfigurationError,
    UnsupportedAudioFormatError,
)
from tts.models import AudioFormat, SynthesizedAudio

logger = logging.getLogger(__name__)


class Synthesizer(ABC):
    """Turns text into audio without exposing provider-specific details."""

    @abstractmethod
    async def synthesize(
        self,
        *,
        text: str,
        language: str,
        voice: str,
        speed: float,
        output_format: AudioFormat,
    ) -> SynthesizedAudio: ...


class ElevenLabsTextToSpeechClient(Protocol):
    # The generated SDK has a large, version-dependent keyword surface. Any is intentionally
    # confined to this provider boundary; the Synthesizer interface above remains fully typed.
    def convert(self, voice_id: str, **kwargs: Any) -> AsyncIterator[bytes]: ...


class ElevenLabsClient(Protocol):
    @property
    def text_to_speech(self) -> ElevenLabsTextToSpeechClient: ...


@dataclass(frozen=True)
class _ElevenLabsFormat:
    provider_name: str
    media_type: str
    file_extension: str


_ELEVENLABS_FORMATS: dict[AudioFormat, _ElevenLabsFormat] = {
    "mp3": _ElevenLabsFormat(
        provider_name="mp3_44100_128",
        media_type="audio/mpeg",
        file_extension="mp3",
    ),
    "mp3_fast": _ElevenLabsFormat(
        provider_name="mp3_22050_32",
        media_type="audio/mpeg",
        file_extension="mp3",
    ),
    "wav": _ElevenLabsFormat(
        provider_name="wav_44100",
        media_type="audio/wav",
        file_extension="wav",
    ),
}


class ElevenLabsSynthesizer(Synthesizer):
    """Text-to-speech through the ElevenLabs streaming API."""

    def __init__(self, *, client: ElevenLabsClient, model: str) -> None:
        normalized_model = model.strip()
        if not normalized_model:
            raise TTSConfigurationError("ElevenLabs TTS model must not be empty")
        self._client = client
        self._model = normalized_model

    async def synthesize(
        self,
        *,
        text: str,
        language: str,
        voice: str,
        speed: float,
        output_format: AudioFormat,
    ) -> SynthesizedAudio:
        try:
            format_info = _ELEVENLABS_FORMATS[output_format]
        except KeyError as exc:
            raise UnsupportedAudioFormatError(output_format) from exc

        try:
            stream = self._client.text_to_speech.convert(
                voice,
                text=text,
                model_id=self._model,
                language_code=language,
                output_format=format_info.provider_name,
                voice_settings=VoiceSettings(speed=speed),
            )
            data = b"".join([chunk async for chunk in stream])
        except Exception as exc:
            logger.error("elevenlabs speech synthesis failed", exc_info=exc)
            raise SpeechSynthesisFailedError("speech synthesis failed") from exc

        if not data:
            raise SpeechSynthesisFailedError("speech synthesis returned empty audio")

        return SynthesizedAudio(
            data=data,
            media_type=format_info.media_type,
            file_extension=format_info.file_extension,
        )
