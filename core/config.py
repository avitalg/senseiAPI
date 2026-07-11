from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


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

    # Session summaries, generated locally by Ollama so transcripts (PHI) never leave the host.
    summary_enabled: bool = True
    # "ollama" runs a model locally (transcripts stay on this host); "gemini" sends the
    # transcript to Google; "mock" returns canned data for frontend work and CI.
    # Mock is opt-in on purpose: serving invented clinical content by default is not a
    # mistake worth risking in a therapy product.
    summary_backend: Literal["ollama", "gemini", "mock"] = "ollama"
    # Required when summary_backend is "gemini".
    google_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:7b-instruct"
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


def validate_backends(settings: Settings) -> None:
    """Reject a backend selected without the credential it needs.

    Each field is valid on its own; only the pair is wrong, so no type can catch this.
    Called at app startup so a misconfigured deploy dies at boot rather than looking
    healthy until the first therapist uploads a session.

    Deliberately not a pydantic ``model_validator``: that would make ``Settings()``
    itself unconstructible without an API key, which breaks a fresh clone and CI.
    """
    if settings.transcriber_backend == "elevenlabs" and not settings.elevenlabs_api_key:
        raise RuntimeError("ELEVENLABS_API_KEY must be set when TRANSCRIBER_BACKEND=elevenlabs")

    gemini_selected = settings.summary_enabled and settings.summary_backend == "gemini"
    if gemini_selected and not settings.google_api_key:
        raise RuntimeError("GOOGLE_API_KEY must be set when SUMMARY_BACKEND=gemini")


@lru_cache
def get_settings() -> Settings:
    return Settings()
