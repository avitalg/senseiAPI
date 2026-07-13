import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from core.config import Settings, get_settings
from main import app
from patients.dependencies import get_patient_service
from patients.models import Patient, PatientNotFoundError
from reports.dependencies import get_report_reader, get_report_service
from reports.models import ReportStatus, StoredReport
from summaries.dependencies import get_summary_reader
from summaries.models import ReadyMeetingSummary

PATIENT_ID = uuid.UUID("33333333-3333-3333-3333-333333333333")


@pytest.fixture(autouse=True)
def _no_background_generation(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # reports/__init__.py exports `router`, which shadows the submodule name on the
    # package — patch via sys.modules instead.
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
        "id": uuid.uuid4(),
        "patient_id": PATIENT_ID,
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


class _FakePatients:
    def __init__(self, *, exists: bool = True) -> None:
        self.exists = exists

    async def get_patient(self, patient_id: uuid.UUID) -> Patient:
        if not self.exists:
            raise PatientNotFoundError(patient_id)
        return Patient(
            id=patient_id,
            name="Test",
            phone="050",
            email=None,
            created_at=datetime.now(UTC),
        )


class _FakeReportReader:
    def __init__(self, report: StoredReport | None) -> None:
        self._report = report

    async def get_by_patient_id(self, patient_id: uuid.UUID) -> StoredReport | None:
        return self._report


class _FakeSummaryReader:
    def __init__(self, ready: list[ReadyMeetingSummary] | None = None) -> None:
        self._ready = ready or []

    async def list_ready_for_patient(
        self,
        patient_id: uuid.UUID,
        *,
        limit: int = 8,
    ) -> list[ReadyMeetingSummary]:
        return self._ready[:limit]


class _FakeReportService:
    def __init__(self, report: StoredReport | None = None) -> None:
        self.report = report
        self.create_pending = AsyncMock(
            return_value=report or _stored("pending"),
        )
        self.get = AsyncMock(return_value=report)
        self.generate = AsyncMock()


def teardown_function() -> None:
    app.dependency_overrides.clear()


def _client(
    *,
    report: StoredReport | None = None,
    patient_exists: bool = True,
    ready: list[ReadyMeetingSummary] | None = None,
    service: _FakeReportService | None = None,
) -> TestClient:
    svc = service or _FakeReportService(report)
    app.dependency_overrides[get_patient_service] = lambda: _FakePatients(exists=patient_exists)
    app.dependency_overrides[get_report_reader] = lambda: _FakeReportReader(report)
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
            start_at=datetime.now(UTC),
            text="סיכום ארוך לפגישה האחרונה " * 5,
        )
    ]
    client = _client(report=report, ready=ready)

    res = client.get(f"/patients/{PATIENT_ID}/next-meeting-report")

    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ready"
    assert body["intro"] == "סקירה"
    assert body["changes"] == ["א"]
    assert body["open_topics"] == ["ב"]
    assert body["last_summary_excerpt"]


def test_get_running_report_returns_202() -> None:
    client = _client(report=_stored("running"))

    res = client.get(f"/patients/{PATIENT_ID}/next-meeting-report")

    assert res.status_code == 202
    assert res.json()["status"] == "running"


def test_get_missing_report_returns_404() -> None:
    client = _client(report=None)

    res = client.get(f"/patients/{PATIENT_ID}/next-meeting-report")

    assert res.status_code == 404


def test_post_unknown_patient_returns_404() -> None:
    client = _client(patient_exists=False)

    res = client.post(f"/patients/{PATIENT_ID}/next-meeting-report")

    assert res.status_code == 404


def test_post_starts_generation_for_new_report() -> None:
    pending = _stored("pending")
    svc = _FakeReportService(None)
    svc.get = AsyncMock(return_value=None)
    svc.create_pending = AsyncMock(return_value=pending)
    client = _client(report=None, service=svc)

    res = client.post(f"/patients/{PATIENT_ID}/next-meeting-report")

    assert res.status_code == 202
    assert res.json()["status"] == "pending"
    svc.create_pending.assert_awaited_once_with(PATIENT_ID)


def test_post_returns_inflight_without_reset() -> None:
    running = _stored("running")
    svc = _FakeReportService(running)
    svc.get = AsyncMock(return_value=running)
    client = _client(report=running, service=svc)

    res = client.post(f"/patients/{PATIENT_ID}/next-meeting-report")

    assert res.status_code == 202
    assert res.json()["status"] == "running"
    svc.create_pending.assert_not_awaited()


def test_get_failed_report_returns_200_with_error() -> None:
    client = _client(report=_stored("failed", error="אין סיכומי פגישות מוכנים"))

    res = client.get(f"/patients/{PATIENT_ID}/next-meeting-report")

    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "failed"
    assert body["error"] == "אין סיכומי פגישות מוכנים"
