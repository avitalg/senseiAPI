import sys
import uuid
from datetime import UTC, date, datetime
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from auth.router import TEST_USER_ID
from core.config import Settings, get_settings
from daily_reports.dependencies import get_daily_report_service
from daily_reports.models import DailyReportStatus, StoredDailyReport
from main import app
from tts.models import SynthesizedAudio

REPORT_ID = uuid.UUID("33333333-3333-3333-3333-333333333333")
REPORT_DATE = date(2026, 7, 21)
NOW = datetime(2026, 7, 21, 6, 0, tzinfo=UTC)


def _stored(status: DailyReportStatus, **changes: object) -> StoredDailyReport:
    base: dict[str, object] = {
        "user_id": TEST_USER_ID,
        "id": REPORT_ID,
        "report_date": REPORT_DATE,
        "time_zone": "Asia/Jerusalem",
        "status": status,
        "meeting_limit": 4,
        "meeting_count": 0,
        "text": None,
        "source_meeting_ids": [],
        "source_report_ids": [],
        "model": "",
        "prompt_version": "",
        "error": None,
        "created_at": NOW,
        "updated_at": NOW,
    }
    base.update(changes)
    return StoredDailyReport(**base)  # type: ignore[arg-type]


class _FakeDailyService:
    def __init__(
        self,
        report: StoredDailyReport | None,
        *,
        should_generate: bool = False,
    ) -> None:
        self.request_report = AsyncMock(return_value=(report, should_generate))
        self.get = AsyncMock(return_value=report)


class _FakeTTSService:
    def __init__(
        self,
        *,
        audio: SynthesizedAudio | None = None,
        error: Exception | None = None,
    ) -> None:
        self._audio = audio
        self._error = error
        self.calls: list[dict[str, object]] = []

    async def synthesize(
        self,
        *,
        text: str,
        speed: float | None = None,
    ) -> SynthesizedAudio:
        self.calls.append({"text": text, "speed": speed})
        if self._error is not None:
            raise self._error
        assert self._audio is not None
        return self._audio


def _patch_tts(
    monkeypatch: pytest.MonkeyPatch,
    *,
    service: _FakeTTSService | None = None,
    config_error: Exception | None = None,
) -> None:
    def fake_build_tts_service(settings: Settings) -> _FakeTTSService:
        if config_error is not None:
            raise config_error
        assert service is not None
        return service

    monkeypatch.setattr(
        sys.modules["daily_reports.router"],
        "build_tts_service",
        fake_build_tts_service,
    )


@pytest.fixture(autouse=True)
def _daily_api_dependencies(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    settings = Settings(
        upload_dir=tmp_path / "uploads",
        enable_security=False,
        auth_token_secret_key=None,
        database_url=None,
    )
    app.dependency_overrides[get_settings] = lambda: settings
    monkeypatch.setattr(
        sys.modules["daily_reports.router"],
        "run_daily_report_generation",
        AsyncMock(),
    )


def teardown_function() -> None:
    app.dependency_overrides.clear()


def _client(service: _FakeDailyService) -> TestClient:
    app.dependency_overrides[get_daily_report_service] = lambda: service
    return TestClient(app)


def test_post_starts_daily_report_with_query_parameters() -> None:
    pending = _stored("pending")
    service = _FakeDailyService(pending, should_generate=True)
    client = _client(service)

    response = client.post(
        "/daily-meeting-reports?report_date=2026-07-21&time_zone=Asia/Jerusalem&meeting_limit=4"
    )

    assert response.status_code == 202
    assert response.json()["id"] == str(REPORT_ID)
    assert response.json()["status"] == "pending"
    service.request_report.assert_awaited_once_with(
        TEST_USER_ID,
        REPORT_DATE,
        time_zone="Asia/Jerusalem",
        meeting_limit=4,
        refresh=False,
    )


def test_post_refresh_one_is_parsed_as_true() -> None:
    pending = _stored("pending")
    service = _FakeDailyService(pending, should_generate=True)
    client = _client(service)

    response = client.post("/daily-meeting-reports?report_date=2026-07-21&refresh=1")

    assert response.status_code == 202
    await_args = service.request_report.await_args
    assert await_args is not None
    assert await_args.kwargs["refresh"] is True


def test_post_returns_cached_ready_report_without_patient_array() -> None:
    ready = _stored(
        "ready",
        meeting_count=4,
        text="תדריך יומי קצר.",
        model="daily-model",
    )
    service = _FakeDailyService(ready)
    client = _client(service)

    response = client.post("/daily-meeting-reports?report_date=2026-07-21")

    assert response.status_code == 200
    body = response.json()
    assert body["text"] == "תדריך יומי קצר."
    assert body["meeting_count"] == 4
    assert "patients" not in body
    assert "ready_patient_count" not in body


def test_post_rejects_invalid_time_zone() -> None:
    service = _FakeDailyService(_stored("pending"))
    client = _client(service)

    response = client.post("/daily-meeting-reports?time_zone=bad-zone")

    assert response.status_code == 400
    assert response.json()["detail"] == "invalid time_zone"
    service.request_report.assert_not_awaited()


@pytest.mark.parametrize("meeting_limit", [0, 21])
def test_post_rejects_meeting_limit_outside_bounds(meeting_limit: int) -> None:
    service = _FakeDailyService(_stored("pending"))
    client = _client(service)

    response = client.post(f"/daily-meeting-reports?meeting_limit={meeting_limit}")

    assert response.status_code == 422


def test_get_running_report_returns_202() -> None:
    service = _FakeDailyService(_stored("running"))
    client = _client(service)

    response = client.get(f"/daily-meeting-reports/{REPORT_ID}")

    assert response.status_code == 202
    assert response.json()["status"] == "running"


def test_get_ready_report_returns_single_text() -> None:
    service = _FakeDailyService(_stored("ready", meeting_count=2, text="היום צפויות שתי פגישות."))
    client = _client(service)

    response = client.get(f"/daily-meeting-reports/{REPORT_ID}")

    assert response.status_code == 200
    assert response.json()["text"] == "היום צפויות שתי פגישות."
    assert response.json()["generated_at"] == NOW.isoformat()
    service.get.assert_awaited_once_with(TEST_USER_ID, REPORT_ID)


def test_get_missing_report_returns_404() -> None:
    service = _FakeDailyService(None)
    client = _client(service)

    response = client.get(f"/daily-meeting-reports/{REPORT_ID}")

    assert response.status_code == 404


def test_get_daily_report_speech_returns_audio_with_defaults(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report = _stored("ready", text="תדריך יומי קצר.")
    audio = SynthesizedAudio(
        data=b"fake-audio-bytes",
        media_type="audio/mpeg",
        file_extension="mp3",
    )
    tts = _FakeTTSService(audio=audio)
    _patch_tts(monkeypatch, service=tts)
    client = _client(_FakeDailyService(report))

    response = client.get(f"/daily-meeting-reports/{REPORT_ID}/speech")

    assert response.status_code == 200
    assert response.content == b"fake-audio-bytes"
    assert response.headers["content-type"] == "audio/mpeg"
    assert tts.calls == [
        {
            "text": "תדריך יומי קצר.",
            "speed": 1.0,
        }
    ]


def test_get_daily_report_speech_forwards_speed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report = _stored("ready", text="תדריך יומי.")
    audio = SynthesizedAudio(
        data=b"audio",
        media_type="audio/wav",
        file_extension="wav",
    )
    tts = _FakeTTSService(audio=audio)
    _patch_tts(monkeypatch, service=tts)
    client = _client(_FakeDailyService(report))

    response = client.get(f"/daily-meeting-reports/{REPORT_ID}/speech?speed=0.8")

    assert response.status_code == 200
    assert response.headers["content-type"] == "audio/wav"
    assert tts.calls == [{"text": "תדריך יומי.", "speed": 0.8}]


@pytest.mark.parametrize("report_status", ["pending", "running"])
def test_get_daily_report_speech_generating_returns_409(
    report_status: DailyReportStatus,
) -> None:
    client = _client(_FakeDailyService(_stored(report_status)))

    response = client.get(f"/daily-meeting-reports/{REPORT_ID}/speech")

    assert response.status_code == 409
    assert response.json()["detail"] == "daily meeting report is still generating"


def test_get_daily_report_speech_failed_returns_409() -> None:
    client = _client(_FakeDailyService(_stored("failed", error="generation failed")))

    response = client.get(f"/daily-meeting-reports/{REPORT_ID}/speech")

    assert response.status_code == 409
    assert response.json()["detail"] == "generation failed"


def test_get_daily_report_speech_missing_returns_404() -> None:
    client = _client(_FakeDailyService(None))

    response = client.get(f"/daily-meeting-reports/{REPORT_ID}/speech")

    assert response.status_code == 404
    assert response.json()["detail"] == "daily meeting report not found"


def test_get_daily_report_speech_tts_disabled_returns_503(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tts.errors import TTSConfigurationError

    _patch_tts(monkeypatch, config_error=TTSConfigurationError("TTS is disabled"))
    client = _client(_FakeDailyService(_stored("ready", text="תדריך")))

    response = client.get(f"/daily-meeting-reports/{REPORT_ID}/speech")

    assert response.status_code == 503
    assert response.json()["detail"] == "text-to-speech is not available"


@pytest.mark.parametrize(
    "error",
    [
        pytest.param("empty", id="empty-text"),
        pytest.param("too-long", id="text-too-long"),
        pytest.param("speed", id="invalid-speed"),
    ],
)
def test_get_daily_report_speech_invalid_request_returns_422(
    monkeypatch: pytest.MonkeyPatch,
    error: str,
) -> None:
    from tts.errors import (
        EmptyTextError,
        InvalidSpeechSpeedError,
        TextTooLongError,
    )

    errors: dict[str, Exception] = {
        "empty": EmptyTextError("text must not be empty"),
        "too-long": TextTooLongError(6_000, 5_000),
        "speed": InvalidSpeechSpeedError(2.0, 0.7, 1.2),
    }
    _patch_tts(monkeypatch, service=_FakeTTSService(error=errors[error]))
    client = _client(_FakeDailyService(_stored("ready", text="תדריך")))

    response = client.get(f"/daily-meeting-reports/{REPORT_ID}/speech")

    assert response.status_code == 422


def test_get_daily_report_speech_synthesis_failure_returns_502(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tts.errors import SpeechSynthesisFailedError

    _patch_tts(
        monkeypatch,
        service=_FakeTTSService(error=SpeechSynthesisFailedError("provider failed")),
    )
    client = _client(_FakeDailyService(_stored("ready", text="תדריך")))

    response = client.get(f"/daily-meeting-reports/{REPORT_ID}/speech")

    assert response.status_code == 502
    assert response.json()["detail"] == "failed to synthesize speech"


@pytest.mark.parametrize("query", ["speed=0.69", "speed=1.21"])
def test_get_daily_report_speech_rejects_invalid_query(query: str) -> None:
    service = _FakeDailyService(_stored("ready", text="תדריך"))
    client = _client(service)

    response = client.get(f"/daily-meeting-reports/{REPORT_ID}/speech?{query}")

    assert response.status_code == 422
    service.get.assert_not_awaited()
