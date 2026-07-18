from tts.errors import (
    EmptyTextError,
    InvalidLanguageError,
    InvalidSpeechSpeedError,
    InvalidVoiceError,
    TextTooLongError,
    TTSConfigurationError,
    UnsupportedAudioFormatError,
)
from tts.models import AudioFormat, SynthesizedAudio
from tts.synthesizer import Synthesizer

MIN_SPEECH_SPEED = 0.7
MAX_SPEECH_SPEED = 1.2
SUPPORTED_AUDIO_FORMATS: tuple[AudioFormat, ...] = ("mp3", "wav")


class TTSService:
    """Validates text-to-speech requests and applies application defaults."""

    def __init__(
        self,
        *,
        synthesizer: Synthesizer,
        default_voice: str,
        default_language: str = "he",
        default_speed: float = 1.0,
        default_output_format: AudioFormat = "mp3",
        max_text_chars: int = 5_000,
    ) -> None:
        normalized_voice = default_voice.strip()
        normalized_language = default_language.strip()
        if not normalized_voice:
            raise TTSConfigurationError("default TTS voice must not be empty")
        if not normalized_language:
            raise TTSConfigurationError("default TTS language must not be empty")
        if not MIN_SPEECH_SPEED <= default_speed <= MAX_SPEECH_SPEED:
            raise TTSConfigurationError(
                f"default TTS speed must be between {MIN_SPEECH_SPEED} and {MAX_SPEECH_SPEED}"
            )
        if default_output_format not in SUPPORTED_AUDIO_FORMATS:
            raise TTSConfigurationError(
                f"unsupported default TTS audio format: {default_output_format!r}"
            )
        if max_text_chars <= 0:
            raise TTSConfigurationError("TTS text limit must be positive")

        self._synthesizer = synthesizer
        self._default_voice = normalized_voice
        self._default_language = normalized_language
        self._default_speed = default_speed
        self._default_output_format = default_output_format
        self._max_text_chars = max_text_chars

    async def synthesize(
        self,
        *,
        text: str,
        language: str | None = None,
        voice: str | None = None,
        speed: float | None = None,
        output_format: AudioFormat | None = None,
    ) -> SynthesizedAudio:
        normalized_text = text.strip()
        if not normalized_text:
            raise EmptyTextError("text must not be empty")
        if len(normalized_text) > self._max_text_chars:
            raise TextTooLongError(len(normalized_text), self._max_text_chars)

        resolved_language = self._default_language if language is None else language.strip()
        if not resolved_language:
            raise InvalidLanguageError("language must not be empty")

        resolved_voice = self._default_voice if voice is None else voice.strip()
        if not resolved_voice:
            raise InvalidVoiceError("voice must not be empty")

        resolved_speed = self._default_speed if speed is None else speed
        if not MIN_SPEECH_SPEED <= resolved_speed <= MAX_SPEECH_SPEED:
            raise InvalidSpeechSpeedError(
                resolved_speed,
                MIN_SPEECH_SPEED,
                MAX_SPEECH_SPEED,
            )

        resolved_format = self._default_output_format if output_format is None else output_format
        if resolved_format not in SUPPORTED_AUDIO_FORMATS:
            raise UnsupportedAudioFormatError(resolved_format)

        return await self._synthesizer.synthesize(
            text=normalized_text,
            language=resolved_language,
            voice=resolved_voice,
            speed=resolved_speed,
            output_format=resolved_format,
        )
