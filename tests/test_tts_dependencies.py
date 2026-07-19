from collections.abc import AsyncIterator

import pytest

from core.config import Settings
from tts import dependencies as tts_dependencies
from tts.dependencies import get_synthesizer, get_tts_service
from tts.errors import TextTooLongError, TTSConfigurationError
from tts.models import AudioFormat, SynthesizedAudio
from tts.synthesizer import ElevenLabsClient, ElevenLabsSynthesizer, Synthesizer


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def _settings(
    *,
    enabled: bool = True,
    api_key: str | None = "api-key",
    voice_id: str | None = "voice-id",
    timeout_seconds: int = 30,
) -> Settings:
    return Settings(
        enable_security=False,
        tts_enabled=enabled,
        elevenlabs_api_key=api_key,
        elevenlabs_tts_voice_id=voice_id,
        elevenlabs_tts_model="tts-model",
        tts_timeout_seconds=timeout_seconds,
    )


class _FakeTextToSpeech:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []

    async def convert(self, voice_id: str, **kwargs: object) -> AsyncIterator[bytes]:
        self.calls.append((voice_id, kwargs))
        yield b"audio"


class _FakeElevenLabsClient:
    def __init__(self) -> None:
        self.text_to_speech = _FakeTextToSpeech()


@pytest.mark.anyio
async def test_get_synthesizer_builds_async_elevenlabs_adapter_from_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _FakeElevenLabsClient()
    client_arguments: dict[str, object] = {}

    def build_client(*, api_key: str, timeout_seconds: int) -> ElevenLabsClient:
        client_arguments.update(api_key=api_key, timeout_seconds=timeout_seconds)
        return client

    monkeypatch.setattr(tts_dependencies, "_build_elevenlabs_client", build_client)

    synthesizer = get_synthesizer(_settings(timeout_seconds=45))
    result = await synthesizer.synthesize(
        text="שלום",
        language="he",
        voice="voice-id",
        speed=1.0,
        output_format="mp3",
    )

    assert isinstance(synthesizer, ElevenLabsSynthesizer)
    assert client_arguments == {"api_key": "api-key", "timeout_seconds": 45}
    assert result.data == b"audio"
    assert client.text_to_speech.calls[0][1]["model_id"] == "tts-model"


@pytest.mark.parametrize("api_key", [None, "", " "])
def test_get_synthesizer_requires_api_key(api_key: str | None) -> None:
    with pytest.raises(TTSConfigurationError, match="ELEVENLABS_API_KEY"):
        get_synthesizer(_settings(api_key=api_key))


def test_get_synthesizer_rejects_disabled_tts() -> None:
    with pytest.raises(TTSConfigurationError, match="disabled"):
        get_synthesizer(_settings(enabled=False))


@pytest.mark.parametrize("timeout_seconds", [0, -1])
def test_get_synthesizer_rejects_non_positive_timeout(timeout_seconds: int) -> None:
    with pytest.raises(TTSConfigurationError, match="TTS_TIMEOUT_SECONDS"):
        get_synthesizer(_settings(timeout_seconds=timeout_seconds))


class _RecordingSynthesizer(Synthesizer):
    def __init__(self) -> None:
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
        return SynthesizedAudio(b"audio", "audio/mpeg", "mp3")


@pytest.mark.anyio
async def test_get_tts_service_applies_all_configured_defaults() -> None:
    settings = _settings(voice_id="configured-voice")
    settings.tts_default_language = "en"
    settings.tts_default_speed = 0.8
    settings.tts_default_output_format = "wav"
    settings.tts_max_text_chars = 4
    synthesizer = _RecordingSynthesizer()
    service = get_tts_service(synthesizer=synthesizer, settings=settings)

    await service.synthesize(text="test")

    assert synthesizer.calls == [
        {
            "text": "test",
            "language": "en",
            "voice": "configured-voice",
            "speed": 0.8,
            "output_format": "wav",
        }
    ]
    with pytest.raises(TextTooLongError):
        await service.synthesize(text="12345")


@pytest.mark.parametrize("voice_id", [None, "", " "])
def test_get_tts_service_requires_default_voice(voice_id: str | None) -> None:
    with pytest.raises(TTSConfigurationError, match="ELEVENLABS_TTS_VOICE_ID"):
        get_tts_service(
            synthesizer=_RecordingSynthesizer(),
            settings=_settings(voice_id=voice_id),
        )


def test_get_tts_service_rejects_disabled_tts() -> None:
    with pytest.raises(TTSConfigurationError, match="disabled"):
        get_tts_service(
            synthesizer=_RecordingSynthesizer(),
            settings=_settings(enabled=False),
        )
