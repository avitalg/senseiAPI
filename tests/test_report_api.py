import sys
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from auth.router import TEST_USER_ID
from calendar_events.models import CalendarEvent
from core.config import Settings, get_settings
from main import app
from patients.dependencies import get_patient_service
from patients.models import Patient, PatientNotFoundError
from reports.dependencies import get_report_reader, get_report_service
from reports.models import ReportStatus, StoredReport
from summaries.dependencies import get_summary_reader
from summaries.models import ReadyMeetingSummary
from tts.models import SynthesizedAudio

PATIENT_ID = uuid.UUID("33333333-3333-3333-3333-333333333333")
MEETING_ID = uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
OTHER_MEETING_ID = uuid.UUID("dddddddd-dddd-dddd-dddd-dddddddddddd")
USER_ID = TEST_USER_ID
NOW = datetime(2026, 7, 17, 10, 30, tzinfo=UTC)


@pytest.fixture(autouse=True)
def _no_background_generation(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        sys.modules["reports.router"],
        "run_report_generation",
        AsyncMock(),
    )
    settings = Settings(
        upload_dir=tmp_path / "uploads",
        enable_security=False,
        auth_token_secret_key=None,
        database_url=None,
    )
    app.dependency_overrides[get_settings] = lambda: settings


def _stored(status: ReportStatus, **changes: object) -> StoredReport:
    now = datetime.now(UTC)
    base: dict[str, object] = {
        "user_id": USER_ID,
        "id": uuid.uuid4(),
        "patient_id": PATIENT_ID,
        "meeting_id": MEETING_ID,
        "status": status,
        "intro": None,
        "changes": [],
        "open_topics": [],
        "source_meeting_ids": [],
        "model": "qwen2.5:7b-instruct",
        "error": None,
        "created_at": now,
        "updated_at": now,
    }
    base.update(changes)
    return StoredReport(**base)  # type: ignore[arg-type]


def _meeting(
    meeting_id: uuid.UUID = MEETING_ID,
    *,
    start_at: datetime | None = None,
    end_at: datetime | None = None,
    patient_id: uuid.UUID = PATIENT_ID,
) -> CalendarEvent:
    start = start_at or NOW + timedelta(hours=1)
    end = end_at or start + timedelta(hours=1)
    return CalendarEvent(
        id=meeting_id,
        title="פגישה",
        description=None,
        start_at=start,
        end_at=end,
        created_at=NOW,
        user_id=USER_ID,
        patient_id=patient_id,
    )


class _FakePatients:
    def __init__(self, *, exists: bool = True) -> None:
        self.exists = exists

    async def get_patient(self, user_id: uuid.UUID, patient_id: uuid.UUID) -> Patient:
        if not self.exists:
            raise PatientNotFoundError(patient_id)
        return Patient(
            user_id=user_id,
            id=patient_id,
            name="Test",
            phone="050",
            email=None,
            created_at=datetime.now(UTC),
        )


class _FakeReportReader:
    def __init__(self, reports: dict[uuid.UUID, StoredReport] | StoredReport | None) -> None:
        if isinstance(reports, StoredReport):
            self._reports = {reports.meeting_id: reports}
        elif reports is None:
            self._reports = {}
        else:
            self._reports = reports

    async def get_by_meeting_id(
        self,
        user_id: uuid.UUID,
        meeting_id: uuid.UUID,
    ) -> StoredReport | None:
        return self._reports.get(meeting_id)

    async def list_for_patient(
        self,
        user_id: uuid.UUID,
        patient_id: uuid.UUID,
    ) -> list[StoredReport]:
        return [r for r in self._reports.values() if r.patient_id == patient_id]


class _FakeSummaryReader:
    def __init__(self, ready: list[ReadyMeetingSummary] | None = None) -> None:
        self._ready = ready or []

    async def list_ready_for_patient(
        self,
        user_id: uuid.UUID,
        patient_id: uuid.UUID,
        *,
        limit: int = 8,
    ) -> list[ReadyMeetingSummary]:
        return self._ready[:limit]

    async def list_ready_before_meeting(
        self,
        user_id: uuid.UUID,
        patient_id: uuid.UUID,
        *,
        before_start_at: datetime,
        limit: int = 8,
    ) -> list[ReadyMeetingSummary]:
        filtered = [item for item in self._ready if item.start_at < before_start_at]
        return filtered[:limit]


class _FakeReportService:
    def __init__(
        self,
        report: StoredReport | None = None,
        *,
        meeting: CalendarEvent | None = None,
        now: datetime = NOW,
    ) -> None:
        self.report = report
        self.meeting = meeting or _meeting()
        self.create_pending = AsyncMock(
            return_value=report or _stored("pending"),
        )
        self.get = AsyncMock(return_value=report)
        self.generate = AsyncMock()
        self.verify_meeting_for_patient = AsyncMock(return_value=self.meeting)
        self.resolve_next_meeting = AsyncMock(return_value=self.meeting)
        self.list_for_patient = AsyncMock(
            return_value=[report] if report else [],
        )


class _FakeTTSService:
    def __init__(
        self,
        *,
        audio: SynthesizedAudio | None = None,
        error: Exception | None = None,
    ) -> None:
        self._audio = audio
        self._error = error

    async def synthesize(self, *, text: str) -> SynthesizedAudio:
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

    monkeypatch.setattr(sys.modules["reports.router"], "build_tts_service", fake_build_tts_service)


def teardown_function() -> None:
    app.dependency_overrides.clear()


def _client(
    *,
    report: StoredReport | None = None,
    reports: dict[uuid.UUID, StoredReport] | None = None,
    patient_exists: bool = True,
    ready: list[ReadyMeetingSummary] | None = None,
    service: _FakeReportService | None = None,
) -> TestClient:
    reader_data = reports if reports is not None else report
    svc = service or _FakeReportService(report)
    app.dependency_overrides[get_patient_service] = lambda: _FakePatients(exists=patient_exists)
    app.dependency_overrides[get_report_reader] = lambda: _FakeReportReader(reader_data)
    app.dependency_overrides[get_report_service] = lambda: svc
    app.dependency_overrides[get_summary_reader] = lambda: _FakeSummaryReader(ready)
    return TestClient(app)


def test_get_ready_report_returns_200_with_sections() -> None:
    report = _stored(
        "ready",
        intro="סקירה",
        changes=["א"],
        open_topics=["ב"],
        source_meeting_ids=[uuid.uuid4()],
    )
    ready = [
        ReadyMeetingSummary(
            meeting_id=uuid.uuid4(),
            start_at=NOW - timedelta(hours=1),
            text="סיכום ארוך לפגישה האחרונה " * 5,
        )
    ]
    client = _client(report=report, ready=ready)

    res = client.get(f"/patients/{PATIENT_ID}/meeting-reports/{MEETING_ID}")

    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ready"
    assert body["meeting_id"] == str(MEETING_ID)
    assert body["intro"] == "סקירה"
    assert body["changes"] == ["א"]
    assert body["open_topics"] == ["ב"]
    assert body["last_summary_excerpt"]


def test_get_ready_report_includes_generated_at() -> None:
    generated = datetime(2026, 7, 14, 9, 30, tzinfo=UTC)
    report = _stored("ready", intro="סקירה", updated_at=generated)
    client = _client(report=report)

    res = client.get(f"/patients/{PATIENT_ID}/meeting-reports/{MEETING_ID}")

    assert res.status_code == 200
    assert res.json()["generated_at"] == generated.isoformat()


def test_generated_at_tracks_regeneration() -> None:
    before = datetime(2026, 7, 14, 9, 30, tzinfo=UTC)
    after = datetime(2026, 7, 14, 10, 45, tzinfo=UTC)

    first = _client(report=_stored("ready", updated_at=before))
    first_body = first.get(f"/patients/{PATIENT_ID}/meeting-reports/{MEETING_ID}").json()

    second = _client(report=_stored("ready", updated_at=after))
    second_body = second.get(f"/patients/{PATIENT_ID}/meeting-reports/{MEETING_ID}").json()

    assert first_body["generated_at"] == before.isoformat()
    assert second_body["generated_at"] == after.isoformat()
    assert first_body["generated_at"] != second_body["generated_at"]


def test_get_running_report_returns_202() -> None:
    client = _client(report=_stored("running"))

    res = client.get(f"/patients/{PATIENT_ID}/meeting-reports/{MEETING_ID}")

    assert res.status_code == 202
    assert res.json()["status"] == "running"


def test_get_missing_report_returns_404() -> None:
    client = _client(report=None)

    res = client.get(f"/patients/{PATIENT_ID}/meeting-reports/{MEETING_ID}")

    assert res.status_code == 404


def test_post_unknown_patient_returns_404() -> None:
    client = _client(patient_exists=False)

    res = client.post(f"/patients/{PATIENT_ID}/meeting-reports/{MEETING_ID}")

    assert res.status_code == 404


def test_post_starts_generation_for_new_report() -> None:
    pending = _stored("pending")
    svc = _FakeReportService(None)
    svc.get = AsyncMock(return_value=None)
    svc.create_pending = AsyncMock(return_value=pending)
    client = _client(report=None, service=svc)

    res = client.post(f"/patients/{PATIENT_ID}/meeting-reports/{MEETING_ID}")

    assert res.status_code == 202
    assert res.json()["status"] == "pending"
    svc.create_pending.assert_awaited_once_with(USER_ID, PATIENT_ID, MEETING_ID)


def test_post_returns_inflight_without_reset() -> None:
    running = _stored("running")
    svc = _FakeReportService(running)
    svc.get = AsyncMock(return_value=running)
    client = _client(report=running, service=svc)

    res = client.post(f"/patients/{PATIENT_ID}/meeting-reports/{MEETING_ID}")

    assert res.status_code == 202
    assert res.json()["status"] == "running"
    svc.create_pending.assert_not_awaited()


def test_get_failed_report_returns_200_with_error() -> None:
    client = _client(report=_stored("failed", error="אין סיכומי פגישות מוכנים"))

    res = client.get(f"/patients/{PATIENT_ID}/meeting-reports/{MEETING_ID}")

    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "failed"
    assert body["error"] == "אין סיכומי פגישות מוכנים"


def test_next_meeting_get_delegates_to_resolved_meeting() -> None:
    report = _stored("ready", intro="סקירה")
    meeting = _meeting()
    svc = _FakeReportService(report, meeting=meeting)
    client = _client(report=report, service=svc)

    res = client.get(f"/patients/{PATIENT_ID}/next-meeting-report")

    assert res.status_code == 200
    assert res.json()["meeting_id"] == str(MEETING_ID)
    svc.resolve_next_meeting.assert_awaited_once_with(USER_ID, PATIENT_ID)


def test_next_meeting_post_starts_generation_for_resolved_meeting() -> None:
    pending = _stored("pending")
    meeting = _meeting()
    svc = _FakeReportService(None, meeting=meeting)
    svc.get = AsyncMock(return_value=None)
    svc.create_pending = AsyncMock(return_value=pending)
    client = _client(report=None, service=svc)

    res = client.post(f"/patients/{PATIENT_ID}/next-meeting-report")

    assert res.status_code == 202
    svc.resolve_next_meeting.assert_awaited_once_with(USER_ID, PATIENT_ID)
    svc.create_pending.assert_awaited_once_with(USER_ID, PATIENT_ID, MEETING_ID)


def test_next_meeting_get_without_upcoming_meeting_returns_404() -> None:
    from reports.models import NoUpcomingMeetingError

    svc = _FakeReportService(None)
    svc.resolve_next_meeting = AsyncMock(side_effect=NoUpcomingMeetingError(PATIENT_ID))
    client = _client(report=None, service=svc)

    res = client.get(f"/patients/{PATIENT_ID}/next-meeting-report")

    assert res.status_code == 404


def test_meeting_patient_mismatch_returns_404() -> None:
    from reports.models import MeetingPatientMismatchError

    svc = _FakeReportService(None)
    svc.verify_meeting_for_patient = AsyncMock(
        side_effect=MeetingPatientMismatchError(PATIENT_ID, MEETING_ID),
    )
    client = _client(report=None, service=svc)

    res = client.get(f"/patients/{PATIENT_ID}/meeting-reports/{MEETING_ID}")

    assert res.status_code == 404


def test_get_meeting_report_speech_returns_audio(monkeypatch: pytest.MonkeyPatch) -> None:
    report = _stored("ready", intro="סקירה", changes=["א"], open_topics=["ב"])
    audio = SynthesizedAudio(data=b"fake-audio-bytes", media_type="audio/mpeg", file_extension="mp3")
    _patch_tts(monkeypatch, service=_FakeTTSService(audio=audio))
    client = _client(report=report)

    res = client.get(f"/patients/{PATIENT_ID}/meeting-reports/{MEETING_ID}/speech")

    assert res.status_code == 200
    assert res.content == b"fake-audio-bytes"
    assert res.headers["content-type"] == "audio/mpeg"


def test_get_meeting_report_speech_pending_returns_409() -> None:
    client = _client(report=_stored("pending"))

    res = client.get(f"/patients/{PATIENT_ID}/meeting-reports/{MEETING_ID}/speech")

    assert res.status_code == 409


def test_get_meeting_report_speech_running_returns_409() -> None:
    client = _client(report=_stored("running"))

    res = client.get(f"/patients/{PATIENT_ID}/meeting-reports/{MEETING_ID}/speech")

    assert res.status_code == 409


def test_get_meeting_report_speech_failed_returns_409() -> None:
    client = _client(report=_stored("failed", error="אין סיכומי פגישות מוכנים"))

    res = client.get(f"/patients/{PATIENT_ID}/meeting-reports/{MEETING_ID}/speech")

    assert res.status_code == 409
    assert res.json()["detail"] == "אין סיכומי פגישות מוכנים"


def test_get_meeting_report_speech_tts_disabled_returns_503(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tts.errors import TTSConfigurationError

    _patch_tts(monkeypatch, config_error=TTSConfigurationError("TTS is disabled"))
    client = _client(report=_stored("ready", intro="סקירה"))

    res = client.get(f"/patients/{PATIENT_ID}/meeting-reports/{MEETING_ID}/speech")

    assert res.status_code == 503


def test_get_meeting_report_speech_empty_text_returns_422(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tts.errors import EmptyTextError

    fake = _FakeTTSService(error=EmptyTextError("text must not be empty"))
    _patch_tts(monkeypatch, service=fake)
    client = _client(report=_stored("ready", intro=None, changes=[], open_topics=[]))

    res = client.get(f"/patients/{PATIENT_ID}/meeting-reports/{MEETING_ID}/speech")

    assert res.status_code == 422


def test_get_meeting_report_speech_synthesis_failure_returns_502(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tts.errors import SpeechSynthesisFailedError

    fake = _FakeTTSService(error=SpeechSynthesisFailedError("boom"))
    _patch_tts(monkeypatch, service=fake)
    client = _client(report=_stored("ready", intro="סקירה"))

    res = client.get(f"/patients/{PATIENT_ID}/meeting-reports/{MEETING_ID}/speech")

    assert res.status_code == 502


def test_get_meeting_report_speech_missing_report_returns_404() -> None:
    client = _client(report=None)

    res = client.get(f"/patients/{PATIENT_ID}/meeting-reports/{MEETING_ID}/speech")

    assert res.status_code == 404


def test_meeting_report_speech_meeting_not_found_returns_404() -> None:
    from calendar_events.models import CalendarEventNotFoundError

    svc = _FakeReportService(None)
    svc.verify_meeting_for_patient = AsyncMock(
        side_effect=CalendarEventNotFoundError(MEETING_ID),
    )
    client = _client(report=None, service=svc)

    res = client.get(f"/patients/{PATIENT_ID}/meeting-reports/{MEETING_ID}/speech")

    assert res.status_code == 404


def test_meeting_report_speech_patient_mismatch_returns_404() -> None:
    from reports.models import MeetingPatientMismatchError

    svc = _FakeReportService(None)
    svc.verify_meeting_for_patient = AsyncMock(
        side_effect=MeetingPatientMismatchError(PATIENT_ID, MEETING_ID),
    )
    client = _client(report=None, service=svc)

    res = client.get(f"/patients/{PATIENT_ID}/meeting-reports/{MEETING_ID}/speech")

    assert res.status_code == 404


def test_get_meeting_report_speech_unknown_patient_returns_404() -> None:
    client = _client(patient_exists=False)

    res = client.get(f"/patients/{PATIENT_ID}/meeting-reports/{MEETING_ID}/speech")

    assert res.status_code == 404


def test_list_meeting_reports_for_patient() -> None:
    report_a = _stored("ready", meeting_id=MEETING_ID)
    report_b = _stored("failed", meeting_id=OTHER_MEETING_ID, error="x")
    svc = _FakeReportService(report_a)
    svc.list_for_patient = AsyncMock(return_value=[report_a, report_b])
    client = _client(reports={MEETING_ID: report_a, OTHER_MEETING_ID: report_b}, service=svc)

    res = client.get(f"/patients/{PATIENT_ID}/meeting-reports")

    assert res.status_code == 200
    body = res.json()
    assert len(body) == 2
    assert body[0]["meeting_id"] == str(MEETING_ID)
    assert body[1]["status"] == "failed"
