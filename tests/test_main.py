import pytest
from fastapi.testclient import TestClient

from core.config import Settings, SettingsConfigurationError, validate_startup_settings
from main import app

client = TestClient(app)


def test_root_returns_welcome() -> None:
    res = client.get("/")
    assert res.status_code == 200
    assert res.json() == {"message": "Welcome to SenseiAPI"}


def test_health_returns_ok() -> None:
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}


def test_readiness_returns_ready_when_database_ping_succeeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def ping_database_succeeds(settings: Settings) -> bool:
        return True

    monkeypatch.setattr("main.ping_database", ping_database_succeeds)

    res = client.get("/ready")
    assert res.status_code == 200
    assert res.json() == {"status": "ready", "database": "ok"}


def test_readiness_returns_503_when_database_ping_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def ping_database_fails(settings: Settings) -> bool:
        raise OSError("database unavailable")

    monkeypatch.setattr("main.ping_database", ping_database_fails)

    res = client.get("/ready")
    assert res.status_code == 503
    assert res.json() == {"status": "not_ready", "database": "unavailable"}


def test_settings_reads_database_url_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    database_url = "postgresql+asyncpg://user:password@localhost:5432/testdb"
    monkeypatch.setenv("DATABASE_URL", database_url)

    settings = Settings()

    assert settings.database_url == database_url


def test_settings_reads_cors_origins_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:3110,http://127.0.0.1:3110")

    settings = Settings()

    assert settings.cors_origins == "http://localhost:3110,http://127.0.0.1:3110"


def test_settings_reads_tts_configuration_from_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TTS_ENABLED", "true")
    monkeypatch.setenv("TTS_BACKEND", "elevenlabs")
    monkeypatch.setenv("ELEVENLABS_TTS_MODEL", "tts-model")
    monkeypatch.setenv("ELEVENLABS_TTS_VOICE_ID", "voice-id")
    monkeypatch.setenv("TTS_DEFAULT_LANGUAGE", "he")
    monkeypatch.setenv("TTS_DEFAULT_SPEED", "0.9")
    monkeypatch.setenv("TTS_DEFAULT_OUTPUT_FORMAT", "wav")
    monkeypatch.setenv("TTS_MAX_TEXT_CHARS", "4000")
    monkeypatch.setenv("TTS_TIMEOUT_SECONDS", "45")

    settings = Settings()

    assert settings.tts_enabled is True
    assert settings.tts_backend == "elevenlabs"
    assert settings.elevenlabs_tts_model == "tts-model"
    assert settings.elevenlabs_tts_voice_id == "voice-id"
    assert settings.tts_default_language == "he"
    assert settings.tts_default_speed == 0.9
    assert settings.tts_default_output_format == "wav"
    assert settings.tts_max_text_chars == 4000
    assert settings.tts_timeout_seconds == 45


def test_startup_settings_requires_auth_secret_when_security_enabled() -> None:
    settings = Settings(enable_security=True, auth_token_secret_key=None)

    with pytest.raises(SettingsConfigurationError, match="AUTH_TOKEN_SECRET_KEY"):
        validate_startup_settings(settings)


def test_startup_settings_rejects_short_auth_secret() -> None:
    settings = Settings(enable_security=True, auth_token_secret_key="short")

    with pytest.raises(SettingsConfigurationError, match="at least"):
        validate_startup_settings(settings)


def test_startup_settings_rejects_non_positive_token_ttl() -> None:
    settings = Settings(
        enable_security=True,
        auth_token_secret_key="a" * 64,
        auth_token_ttl_seconds=0,
    )

    with pytest.raises(SettingsConfigurationError, match="positive"):
        validate_startup_settings(settings)


def _enabled_tts_settings(
    *,
    api_key: str | None = "test-api-key",
    voice_id: str | None = "voice-id",
    model: str = "eleven_multilingual_v2",
    language: str = "he",
    speed: float = 1.0,
    max_text_chars: int = 5_000,
    timeout_seconds: int = 30,
) -> Settings:
    return Settings(
        enable_security=False,
        tts_enabled=True,
        elevenlabs_api_key=api_key,
        elevenlabs_tts_voice_id=voice_id,
        elevenlabs_tts_model=model,
        tts_default_language=language,
        tts_default_speed=speed,
        tts_max_text_chars=max_text_chars,
        tts_timeout_seconds=timeout_seconds,
    )


def test_startup_settings_accepts_valid_tts_configuration() -> None:
    validate_startup_settings(_enabled_tts_settings())


def test_startup_settings_ignores_tts_credentials_when_disabled() -> None:
    settings = Settings(
        enable_security=False,
        tts_enabled=False,
        elevenlabs_api_key=None,
        elevenlabs_tts_voice_id=None,
    )

    validate_startup_settings(settings)


@pytest.mark.parametrize("api_key", [None, "", " "])
def test_startup_settings_requires_tts_api_key(api_key: str | None) -> None:
    settings = _enabled_tts_settings(api_key=api_key)

    with pytest.raises(SettingsConfigurationError, match="ELEVENLABS_API_KEY"):
        validate_startup_settings(settings)


@pytest.mark.parametrize("voice_id", [None, "", " "])
def test_startup_settings_requires_tts_voice_id(voice_id: str | None) -> None:
    settings = _enabled_tts_settings(voice_id=voice_id)

    with pytest.raises(SettingsConfigurationError, match="ELEVENLABS_TTS_VOICE_ID"):
        validate_startup_settings(settings)


def test_startup_settings_rejects_empty_tts_model() -> None:
    settings = _enabled_tts_settings(model=" ")

    with pytest.raises(SettingsConfigurationError, match="ELEVENLABS_TTS_MODEL"):
        validate_startup_settings(settings)


def test_startup_settings_rejects_empty_tts_language() -> None:
    settings = _enabled_tts_settings(language=" ")

    with pytest.raises(SettingsConfigurationError, match="TTS_DEFAULT_LANGUAGE"):
        validate_startup_settings(settings)


@pytest.mark.parametrize("speed", [0.69, 1.21])
def test_startup_settings_rejects_unsupported_tts_speed(speed: float) -> None:
    settings = _enabled_tts_settings(speed=speed)

    with pytest.raises(SettingsConfigurationError, match="TTS_DEFAULT_SPEED"):
        validate_startup_settings(settings)


@pytest.mark.parametrize("max_text_chars", [0, -1])
def test_startup_settings_rejects_non_positive_tts_text_limit(max_text_chars: int) -> None:
    settings = _enabled_tts_settings(max_text_chars=max_text_chars)

    with pytest.raises(SettingsConfigurationError, match="TTS_MAX_TEXT_CHARS"):
        validate_startup_settings(settings)


@pytest.mark.parametrize("timeout_seconds", [0, -1])
def test_startup_settings_rejects_non_positive_tts_timeout(timeout_seconds: int) -> None:
    settings = _enabled_tts_settings(timeout_seconds=timeout_seconds)

    with pytest.raises(SettingsConfigurationError, match="TTS_TIMEOUT_SECONDS"):
        validate_startup_settings(settings)


def test_unknown_route_returns_404() -> None:
    res = client.get("/does-not-exist")
    assert res.status_code == 404
