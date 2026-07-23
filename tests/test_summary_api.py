import sys
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from auth.router import TEST_USER_ID
from core.config import Settings, get_settings
from core.database import get_db_session
from main import app
from summaries.dependencies import get_summary_reader, get_summary_service
from summaries.models import StoredSummary, SummaryStatus
from transcripts.models import StoredTranscript

MEETING_ID = uuid.uuid4()
HEBREW_SUMMARY = "## נושאים מרכזיים\nחרדה במהלך השבוע."

__import__("summaries.router")


def _stored(status: SummaryStatus, **changes: object) -> StoredSummary:
    now = datetime.now(UTC)
    base: dict[str, object] = {
        "user_id": TEST_USER_ID,
        "id": uuid.uuid4(),
        "meeting_id": MEETING_ID,
        "status": status,
        "text": None,
        "model": "qwen2.5:7b-instruct",
        "error": None,
        "created_at": now,
        "updated_at": now,
    }
    base.update(changes)
    return StoredSummary(**base)  # type: ignore[arg-type]


class _FakeReader:
    def __init__(self, summary: StoredSummary | None) -> None:
        self._summary = summary

    async def get_by_meeting_id(
        self,
        user_id: uuid.UUID,
        meeting_id: uuid.UUID,
    ) -> StoredSummary | None:
        return self._summary


class _FakeSummaryService:
    def __init__(self, summary: StoredSummary | None = None) -> None:
        self.summary = summary or _stored("pending")
        self.get = AsyncMock(return_value=summary)
        self.create_pending = AsyncMock(return_value=self.summary)


class _FakeTranscriptRepo:
    def __init__(self, *, has_transcript: bool = True) -> None:
        self.has_transcript = has_transcript

    async def get_by_meeting_id(
        self,
        user_id: uuid.UUID,
        meeting_id: uuid.UUID,
    ) -> StoredTranscript | None:
        if not self.has_transcript:
            return None
        return StoredTranscript(
            user_id=user_id,
            id=uuid.uuid4(),
            meeting_id=meeting_id,
            raw_text="טקסט",
            diarized_segments=[],
            language="he",
            created_at=datetime.now(UTC),
        )


async def _fake_db_session() -> AsyncIterator[object]:
    yield object()


@pytest.fixture(autouse=True)
def _secure_off(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings(
        upload_dir=tmp_path / "uploads",
        enable_security=False,
        auth_token_secret_key=None,
        database_url=None,
        summary_enabled=True,
    )
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_db_session] = _fake_db_session
    monkeypatch.setattr(
        sys.modules["summaries.router"],
        "run_summary_generation",
        AsyncMock(),
    )


def _client(summary: StoredSummary | None) -> TestClient:
    app.dependency_overrides[get_summary_reader] = lambda: _FakeReader(summary)
    return TestClient(app)


def teardown_function() -> None:
    app.dependency_overrides.clear()


def test_ready_summary_returns_200_with_the_text() -> None:
    client = _client(_stored("ready", text=HEBREW_SUMMARY))

    res = client.get(f"/meetings/{MEETING_ID}/summary")

    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ready"
    assert body["text"] == HEBREW_SUMMARY
    assert body["model"] == "qwen2.5:7b-instruct"
    # The same content, split by heading, alongside the flat text.
    assert body["summary"]["session_main_topics"] == ["חרדה במהלך השבוע."]


def test_ready_summary_splits_every_section() -> None:
    text = (
        "כותרת הפגישה\n\n"
        "מולאן · 24/06/26 · 15:00 · 50 דק׳\n\n"
        "**תובנות מרכזיות**\nתובנה מרכזית אחת.\n\n"
        "**סיכום הפגישה**\nמה קרה בפגישה.\n\n"
        "**נושאים מרכזיים**\n- נושא ראשון\n- נושא שני\n\n"
        "**דגלי סיכון**\n"
        "*(אינדיקטור בלבד. אינו מהווה אבחנה רפואית)*\n"
        "**בינוני** — נדרשת עבודה הדרגתית."
    )
    client = _client(_stored("ready", text=text))

    res = client.get(f"/meetings/{MEETING_ID}/summary")

    assert res.status_code == 200
    summary = res.json()["summary"]
    assert summary["title"] == "כותרת הפגישה"
    assert summary["subtitle"] == "מולאן · 24/06/26 · 15:00 · 50 דק׳"
    assert summary["insights"] == "תובנה מרכזית אחת."
    assert summary["session_summary"] == "מה קרה בפגישה."
    assert summary["session_main_topics"] == ["נושא ראשון", "נושא שני"]
    assert summary["session_risk_flags"]["level"] == "בינוני"
    assert summary["session_risk_flags"]["note"] == "נדרשת עבודה הדרגתית."


def test_unparseable_summary_still_returns_the_text() -> None:
    client = _client(_stored("ready", text="טקסט חופשי בלי כותרות."))

    res = client.get(f"/meetings/{MEETING_ID}/summary")

    assert res.status_code == 200
    body = res.json()
    assert body["text"] == "טקסט חופשי בלי כותרות."
    assert body["summary"] is None


def test_pending_summary_has_no_structured_view() -> None:
    client = _client(_stored("pending"))

    res = client.get(f"/meetings/{MEETING_ID}/summary")

    assert res.status_code == 202
    assert res.json()["summary"] is None


def test_running_summary_returns_202() -> None:
    client = _client(_stored("running"))

    res = client.get(f"/meetings/{MEETING_ID}/summary")

    assert res.status_code == 202
    assert res.json()["status"] == "running"


def test_failed_summary_returns_200_with_the_error() -> None:
    """The request succeeded; it is the summary that failed, and the therapist must see why."""
    client = _client(_stored("failed", error="model qwen2.5 not found"))

    res = client.get(f"/meetings/{MEETING_ID}/summary")

    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "failed"
    assert body["error"] == "model qwen2.5 not found"


def test_missing_summary_returns_404() -> None:
    client = _client(None)

    res = client.get(f"/meetings/{MEETING_ID}/summary")

    assert res.status_code == 404


def test_post_starts_summary_when_transcript_exists(monkeypatch: pytest.MonkeyPatch) -> None:
    pending = _stored("pending")
    svc = _FakeSummaryService(None)
    svc.get = AsyncMock(return_value=None)
    svc.create_pending = AsyncMock(return_value=pending)
    app.dependency_overrides[get_summary_service] = lambda: svc
    monkeypatch.setattr(
        sys.modules["summaries.router"],
        "TranscriptRepository",
        lambda session: _FakeTranscriptRepo(has_transcript=True),
    )

    client = TestClient(app)
    res = client.post(f"/meetings/{MEETING_ID}/summary")

    assert res.status_code == 202
    assert res.json()["status"] == "pending"
    svc.create_pending.assert_awaited_once_with(TEST_USER_ID, MEETING_ID)


def test_post_without_transcript_returns_404(monkeypatch: pytest.MonkeyPatch) -> None:
    svc = _FakeSummaryService(None)
    svc.get = AsyncMock(return_value=None)
    app.dependency_overrides[get_summary_service] = lambda: svc
    monkeypatch.setattr(
        sys.modules["summaries.router"],
        "TranscriptRepository",
        lambda session: _FakeTranscriptRepo(has_transcript=False),
    )

    client = TestClient(app)
    res = client.post(f"/meetings/{MEETING_ID}/summary")

    assert res.status_code == 404
    svc.create_pending.assert_not_awaited()


def test_post_returns_inflight_without_reset() -> None:
    running = _stored("running")
    svc = _FakeSummaryService(running)
    svc.get = AsyncMock(return_value=running)
    app.dependency_overrides[get_summary_service] = lambda: svc

    client = TestClient(app)
    res = client.post(f"/meetings/{MEETING_ID}/summary")

    assert res.status_code == 202
    assert res.json()["status"] == "running"
    svc.create_pending.assert_not_awaited()
