from fastapi import Depends

from core.config import Settings, get_settings
from tts.errors import TTSConfigurationError
from tts.service import TTSService
from tts.synthesizer import ElevenLabsClient, ElevenLabsSynthesizer, Synthesizer


def _build_elevenlabs_client(*, api_key: str, timeout_seconds: int) -> ElevenLabsClient:
    # Imported lazily so disabled TTS never constructs a hosted provider client.
    from elevenlabs.client import AsyncElevenLabs

    return AsyncElevenLabs(api_key=api_key, timeout=timeout_seconds)


def get_synthesizer(settings: Settings = Depends(get_settings)) -> Synthesizer:
    """Build the configured provider adapter for a TTS request."""
    if not settings.tts_enabled:
        raise TTSConfigurationError("TTS is disabled")
    if settings.tts_backend != "elevenlabs":
        raise TTSConfigurationError(f"unsupported TTS backend: {settings.tts_backend!r}")

    api_key = settings.elevenlabs_api_key
    if not api_key or not api_key.strip():
        raise TTSConfigurationError("ELEVENLABS_API_KEY is required for TTS")
    if settings.tts_timeout_seconds <= 0:
        raise TTSConfigurationError("TTS_TIMEOUT_SECONDS must be positive")

    client = _build_elevenlabs_client(
        api_key=api_key,
        timeout_seconds=settings.tts_timeout_seconds,
    )
    return ElevenLabsSynthesizer(
        client=client,
        model=settings.elevenlabs_tts_model,
    )


def get_tts_service(
    synthesizer: Synthesizer = Depends(get_synthesizer),
    settings: Settings = Depends(get_settings),
) -> TTSService:
    """Build a reusable TTS service with application-level defaults."""
    if not settings.tts_enabled:
        raise TTSConfigurationError("TTS is disabled")

    voice_id = settings.elevenlabs_tts_voice_id
    if not voice_id or not voice_id.strip():
        raise TTSConfigurationError("ELEVENLABS_TTS_VOICE_ID is required for TTS")

    return TTSService(
        synthesizer=synthesizer,
        default_voice=voice_id,
        default_language=settings.tts_default_language,
        default_speed=settings.tts_default_speed,
        default_output_format=settings.tts_default_output_format,
        max_text_chars=settings.tts_max_text_chars,
    )
