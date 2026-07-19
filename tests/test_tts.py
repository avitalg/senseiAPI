from collections.abc import AsyncIterator
from typing import cast

import pytest
from elevenlabs.types import VoiceSettings

from tts.errors import (
    EmptyTextError,
    InvalidLanguageError,
    InvalidSpeechSpeedError,
    InvalidVoiceError,
    SpeechSynthesisFailedError,
    TextTooLongError,
    TTSConfigurationError,
    UnsupportedAudioFormatError,
)
from tts.models import AudioFormat, SynthesizedAudio
from tts.service import TTSService
from tts.synthesizer import ElevenLabsSynthesizer, Synthesizer

HEBREW_TEXT = "שלום עולם"
MP3_AUDIO = SynthesizedAudio(
    data=b"fake-mp3-audio",
    media_type="audio/mpeg",
    file_extension="mp3",
)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class _RecordingSynthesizer(Synthesizer):
    def __init__(self, result: SynthesizedAudio = MP3_AUDIO) -> None:
        self._result = result
        self.calls: list[dict[str, object]] = []

    async def synthesize(
        self,
        *,
        text: str,
        language: str,
        voice: str,
        speed: float,
        output_format: AudioFormat,
    ) -> SynthesizedAudio:
        self.calls.append(
            {
                "text": text,
                "language": language,
                "voice": voice,
                "speed": speed,
                "output_format": output_format,
            }
        )
        return self._result


@pytest.mark.anyio
async def test_tts_service_uses_hebrew_defaults_and_trims_text() -> None:
    synthesizer = _RecordingSynthesizer()
    service = TTSService(synthesizer=synthesizer, default_voice="hebrew-voice")

    result = await service.synthesize(text=f"  {HEBREW_TEXT}\n")

    assert result == MP3_AUDIO
    assert synthesizer.calls == [
        {
            "text": HEBREW_TEXT,
            "language": "he",
            "voice": "hebrew-voice",
            "speed": 1.0,
            "output_format": "mp3_fast",
        }
    ]


@pytest.mark.anyio
async def test_tts_service_accepts_per_request_overrides() -> None:
    synthesizer = _RecordingSynthesizer()
    service = TTSService(synthesizer=synthesizer, default_voice="hebrew-voice")

    await service.synthesize(
        text="Hello",
        language="en",
        voice="english-voice",
        speed=0.9,
        output_format="wav",
    )

    assert synthesizer.calls[0] == {
        "text": "Hello",
        "language": "en",
        "voice": "english-voice",
        "speed": 0.9,
        "output_format": "wav",
    }


@pytest.mark.anyio
@pytest.mark.parametrize("text", ["", " ", "\n\t"])
async def test_tts_service_rejects_empty_text(text: str) -> None:
    service = TTSService(synthesizer=_RecordingSynthesizer(), default_voice="voice")

    with pytest.raises(EmptyTextError):
        await service.synthesize(text=text)


@pytest.mark.anyio
async def test_tts_service_rejects_text_over_limit() -> None:
    service = TTSService(
        synthesizer=_RecordingSynthesizer(),
        default_voice="voice",
        max_text_chars=4,
    )

    with pytest.raises(TextTooLongError) as exc_info:
        await service.synthesize(text="12345")

    assert exc_info.value.length == 5
    assert exc_info.value.max_length == 4


@pytest.mark.anyio
async def test_tts_service_rejects_empty_language_override() -> None:
    service = TTSService(synthesizer=_RecordingSynthesizer(), default_voice="voice")

    with pytest.raises(InvalidLanguageError):
        await service.synthesize(text=HEBREW_TEXT, language=" ")


@pytest.mark.anyio
async def test_tts_service_rejects_empty_voice_override() -> None:
    service = TTSService(synthesizer=_RecordingSynthesizer(), default_voice="voice")

    with pytest.raises(InvalidVoiceError):
        await service.synthesize(text=HEBREW_TEXT, voice=" ")


@pytest.mark.anyio
@pytest.mark.parametrize("speed", [0.69, 1.21])
async def test_tts_service_rejects_unsupported_speed(speed: float) -> None:
    service = TTSService(synthesizer=_RecordingSynthesizer(), default_voice="voice")

    with pytest.raises(InvalidSpeechSpeedError):
        await service.synthesize(text=HEBREW_TEXT, speed=speed)


@pytest.mark.anyio
async def test_tts_service_rejects_unsupported_audio_format() -> None:
    service = TTSService(synthesizer=_RecordingSynthesizer(), default_voice="voice")

    with pytest.raises(UnsupportedAudioFormatError):
        await service.synthesize(
            text=HEBREW_TEXT,
            output_format=cast(AudioFormat, "ogg"),
        )


def test_tts_service_rejects_invalid_defaults() -> None:
    synthesizer = _RecordingSynthesizer()

    with pytest.raises(TTSConfigurationError):
        TTSService(synthesizer=synthesizer, default_voice=" ")
    with pytest.raises(TTSConfigurationError):
        TTSService(synthesizer=synthesizer, default_voice="voice", default_language=" ")
    with pytest.raises(TTSConfigurationError):
        TTSService(synthesizer=synthesizer, default_voice="voice", default_speed=2.0)
    with pytest.raises(TTSConfigurationError):
        TTSService(synthesizer=synthesizer, default_voice="voice", max_text_chars=0)


class _FakeTextToSpeech:
    """Stands in for ``AsyncElevenLabs().text_to_speech``."""

    def __init__(
        self,
        *,
        chunks: tuple[bytes, ...] = (),
        error: Exception | None = None,
    ) -> None:
        self._chunks = chunks
        self._error = error
        self.calls: list[tuple[str, dict[str, object]]] = []

    async def convert(self, voice_id: str, **kwargs: object) -> AsyncIterator[bytes]:
        self.calls.append((voice_id, kwargs))
        if self._error is not None:
            raise self._error
        for chunk in self._chunks:
            yield chunk


class _FakeElevenLabsClient:
    def __init__(self, text_to_speech: _FakeTextToSpeech) -> None:
        self.text_to_speech = text_to_speech


@pytest.mark.anyio
async def test_elevenlabs_synthesizer_collects_stream_and_maps_mp3_metadata() -> None:
    text_to_speech = _FakeTextToSpeech(chunks=(b"first-", b"second"))
    synthesizer = ElevenLabsSynthesizer(
        client=_FakeElevenLabsClient(text_to_speech),
        model="eleven_v3",
    )

    result = await synthesizer.synthesize(
        text=HEBREW_TEXT,
        language="he",
        voice="voice-id",
        speed=0.9,
        output_format="mp3",
    )

    assert result == SynthesizedAudio(
        data=b"first-second",
        media_type="audio/mpeg",
        file_extension="mp3",
    )
    voice_id, call = text_to_speech.calls[0]
    assert voice_id == "voice-id"
    assert call["text"] == HEBREW_TEXT
    assert call["language_code"] == "he"
    assert call["model_id"] == "eleven_v3"
    assert call["output_format"] == "mp3_44100_128"
    voice_settings = call["voice_settings"]
    assert isinstance(voice_settings, VoiceSettings)
    assert voice_settings.speed == 0.9


@pytest.mark.anyio
async def test_elevenlabs_synthesizer_maps_wav_metadata() -> None:
    text_to_speech = _FakeTextToSpeech(chunks=(b"wav-audio",))
    synthesizer = ElevenLabsSynthesizer(
        client=_FakeElevenLabsClient(text_to_speech),
        model="eleven_v3",
    )

    result = await synthesizer.synthesize(
        text=HEBREW_TEXT,
        language="he",
        voice="voice-id",
        speed=1.0,
        output_format="wav",
    )

    assert result.media_type == "audio/wav"
    assert result.file_extension == "wav"
    assert text_to_speech.calls[0][1]["output_format"] == "wav_44100"


@pytest.mark.anyio
async def test_elevenlabs_synthesizer_wraps_provider_errors_without_logging_text(
    caplog: pytest.LogCaptureFixture,
) -> None:
    text_to_speech = _FakeTextToSpeech(error=RuntimeError("401 unauthorized"))
    synthesizer = ElevenLabsSynthesizer(
        client=_FakeElevenLabsClient(text_to_speech),
        model="eleven_v3",
    )

    with pytest.raises(SpeechSynthesisFailedError, match="speech synthesis failed"):
        await synthesizer.synthesize(
            text=HEBREW_TEXT,
            language="he",
            voice="voice-id",
            speed=1.0,
            output_format="mp3",
        )

    assert HEBREW_TEXT not in caplog.text


@pytest.mark.anyio
async def test_elevenlabs_synthesizer_rejects_empty_audio() -> None:
    synthesizer = ElevenLabsSynthesizer(
        client=_FakeElevenLabsClient(_FakeTextToSpeech()),
        model="eleven_v3",
    )

    with pytest.raises(SpeechSynthesisFailedError, match="empty audio"):
        await synthesizer.synthesize(
            text=HEBREW_TEXT,
            language="he",
            voice="voice-id",
            speed=1.0,
            output_format="mp3",
        )


def test_elevenlabs_synthesizer_rejects_empty_model() -> None:
    client = _FakeElevenLabsClient(_FakeTextToSpeech())

    with pytest.raises(TTSConfigurationError):
        ElevenLabsSynthesizer(client=client, model=" ")
