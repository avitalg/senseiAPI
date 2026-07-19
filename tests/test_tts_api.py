from collections.abc import AsyncIterator

import pytest

from core import config as core_config
from core.config import Settings
from tts import SynthesizedAudio, text_to_speech
from tts import dependencies as tts_dependencies
from tts.synthesizer import ElevenLabsClient


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class _FakeTextToSpeech:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []

    async def convert(self, voice_id: str, **kwargs: object) -> AsyncIterator[bytes]:
        self.calls.append((voice_id, kwargs))
        yield b"audio-"
        yield b"bytes"


class _FakeElevenLabsClient:
    def __init__(self) -> None:
        self.text_to_speech = _FakeTextToSpeech()


def _settings() -> Settings:
    return Settings(
        enable_security=False,
        tts_enabled=True,
        elevenlabs_api_key="api-key",
        elevenlabs_tts_model="tts-model",
        elevenlabs_tts_voice_id="default-voice",
        tts_default_language="he",
        tts_default_speed=1.0,
        tts_default_output_format="mp3",
    )


@pytest.mark.anyio
async def test_text_to_speech_is_a_complete_internal_api(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings()
    client = _FakeElevenLabsClient()

    def build_client(*, api_key: str, timeout_seconds: int) -> ElevenLabsClient:
        assert api_key == "api-key"
        assert timeout_seconds == 30
        return client

    monkeypatch.setattr(tts_dependencies, "_build_elevenlabs_client", build_client)
    monkeypatch.setattr(core_config, "get_settings", lambda: settings)

    audio = await text_to_speech("  שלום  ")

    assert audio == SynthesizedAudio(
        data=b"audio-bytes",
        media_type="audio/mpeg",
        file_extension="mp3",
    )
    voice_id, call = client.text_to_speech.calls[0]
    assert voice_id == "default-voice"
    assert call["text"] == "שלום"
    assert call["language_code"] == "he"
    assert call["model_id"] == "tts-model"


@pytest.mark.anyio
async def test_text_to_speech_accepts_per_call_overrides(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _FakeElevenLabsClient()

    def build_client(*, api_key: str, timeout_seconds: int) -> ElevenLabsClient:
        return client

    monkeypatch.setattr(tts_dependencies, "_build_elevenlabs_client", build_client)

    audio = await text_to_speech(
        "Hello",
        language="en",
        voice="other-voice",
        speed=0.8,
        output_format="wav",
        settings=_settings(),
    )

    assert audio.media_type == "audio/wav"
    assert audio.file_extension == "wav"
    voice_id, call = client.text_to_speech.calls[0]
    assert voice_id == "other-voice"
    assert call["language_code"] == "en"
    assert call["output_format"] == "wav_44100"
