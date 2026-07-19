from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

from tts.models import MAX_SPEECH_SPEED, MIN_SPEECH_SPEED, AudioFormat

MIN_AUTH_TOKEN_SECRET_BYTES = 32


class Settings(BaseSettings):
    """Application configuration loaded from the environment.

    Override any field via env vars (e.g. ``UPLOAD_DIR``) or a local ``.env``.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    upload_dir: Path = Path("uploads")
    max_upload_bytes: int = 25 * 1024 * 1024  # 25 MiB
    database_url: str | None = "postgresql+asyncpg://sensei:sensei@localhost:5432/senseiapi"

    # Comma-separated browser origins allowed to call the API (e.g. the Vite frontend).
    cors_origins: str = ""

    # Which speech-to-text engine serves transcription requests.
    transcriber_backend: Literal["elevenlabs", "whisper"] = "elevenlabs"

    # ElevenLabs Speech-to-Text (Scribe). Required when the backend is "elevenlabs".
    elevenlabs_api_key: str | None = None
    elevenlabs_model: str = "scribe_v2"

    # Whisper transcription (local, via faster-whisper; no API key needed).
    whisper_model: str = "small"  # tiny|base|small|medium|large-v3 (or a local path)
    whisper_device: str = "cpu"  # "cpu", "cuda", or "auto"
    whisper_compute_type: str = "int8"  # e.g. int8, int8_float16, float16, float32
    transcribe_language: str = "he"  # ISO-639-1; Hebrew by default

    # Text-to-speech is optional and uses the existing ElevenLabs account when enabled.
    tts_enabled: bool = False
    tts_backend: Literal["elevenlabs"] = "elevenlabs"
    elevenlabs_tts_model: str = "eleven_v3"
    elevenlabs_tts_voice_id: str | None = None
    tts_default_language: str = "he"
    tts_default_speed: float = 1.0
    tts_default_output_format: AudioFormat = "mp3_fast"
    tts_max_text_chars: int = 5_000
    tts_timeout_seconds: int = 30

    # Session summaries, generated locally by Ollama so transcripts (PHI) never leave the host.
    summary_enabled: bool = True
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "llama3.1:latest"
    # Ollama defaults num_ctx to 2048 and silently truncates longer input, which would
    # summarise only the opening minutes of a session. Set it explicitly.
    ollama_num_ctx: int = 32768
    ollama_timeout_seconds: int = 600
    # Conservative character budget for the context window above. Hebrew tokenizes less
    # efficiently than English, so this errs toward failing early rather than truncating.
    max_transcript_chars: int = 40_000
    allowed_audio_types: tuple[str, ...] = (
        "audio/mpeg",
        "audio/mp3",
        "audio/wav",
        "audio/x-wav",
        "audio/wave",
        "audio/mp4",
        "audio/x-m4a",
        "audio/m4a",
        "audio/aac",
        "audio/ogg",
        "audio/flac",
        "audio/x-flac",
        "audio/webm",
    )
    enable_security: bool = False
    auth_token_secret_key: str | None = None
    auth_token_ttl_seconds: int = 60 * 60 * 24 * 30


class SettingsConfigurationError(RuntimeError):
    """Raised when startup configuration is invalid."""


def validate_startup_settings(settings: Settings) -> None:
    if settings.enable_security:
        if not settings.auth_token_secret_key:
            raise SettingsConfigurationError(
                "AUTH_TOKEN_SECRET_KEY must be set when ENABLE_SECURITY=true"
            )
        secret_size = len(settings.auth_token_secret_key.encode("utf-8"))
        if secret_size < MIN_AUTH_TOKEN_SECRET_BYTES:
            raise SettingsConfigurationError(
                f"AUTH_TOKEN_SECRET_KEY must be at least {MIN_AUTH_TOKEN_SECRET_BYTES} bytes"
            )
        if settings.auth_token_ttl_seconds <= 0:
            raise SettingsConfigurationError("AUTH_TOKEN_TTL_SECONDS must be positive")

    if settings.tts_enabled:
        if not settings.elevenlabs_api_key or not settings.elevenlabs_api_key.strip():
            raise SettingsConfigurationError("ELEVENLABS_API_KEY must be set when TTS_ENABLED=true")
        if not settings.elevenlabs_tts_voice_id or not settings.elevenlabs_tts_voice_id.strip():
            raise SettingsConfigurationError(
                "ELEVENLABS_TTS_VOICE_ID must be set when TTS_ENABLED=true"
            )
        if not settings.elevenlabs_tts_model.strip():
            raise SettingsConfigurationError("ELEVENLABS_TTS_MODEL must not be empty")
        if not settings.tts_default_language.strip():
            raise SettingsConfigurationError("TTS_DEFAULT_LANGUAGE must not be empty")
        if not MIN_SPEECH_SPEED <= settings.tts_default_speed <= MAX_SPEECH_SPEED:
            raise SettingsConfigurationError(
                f"TTS_DEFAULT_SPEED must be between {MIN_SPEECH_SPEED} and {MAX_SPEECH_SPEED}"
            )
        if settings.tts_max_text_chars <= 0:
            raise SettingsConfigurationError("TTS_MAX_TEXT_CHARS must be positive")
        if settings.tts_timeout_seconds <= 0:
            raise SettingsConfigurationError("TTS_TIMEOUT_SECONDS must be positive")


@lru_cache
def get_settings() -> Settings:
    return Settings()
