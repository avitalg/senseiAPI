"""GET/DELETE /meetings/{id}/transcript — probe and clear for re-upload."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import cast
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from auth.router import TEST_USER_ID
from core.config import Settings, get_settings
from core.database import get_db_session
from main import app
from transcripts.models import StoredTranscript

MEETING_ID = uuid.uuid4()
TRANSCRIPT_ID = uuid.uuid4()


class _FakeSession:
    pass


class _FakeTranscriptRepo:
    def __init__(self, stored: StoredTranscript | None = None) -> None:
        self.stored = stored
        self.delete = AsyncMock(return_value=stored is not None)

    async def get_by_meeting_id(
        self,
        user_id: uuid.UUID,
        meeting_id: uuid.UUID,
    ) -> StoredTranscript | None:
        return self.stored

    async def delete_by_meeting_id(
        self,
        user_id: uuid.UUID,
        meeting_id: uuid.UUID,
    ) -> bool:
        return cast(bool, await self.delete(user_id, meeting_id))


class _FakeSummaryRepo:
    def __init__(self, *, deleted: bool = True) -> None:
        self.delete = AsyncMock(return_value=deleted)

    async def delete_by_meeting_id(
        self,
        user_id: uuid.UUID,
        meeting_id: uuid.UUID,
    ) -> bool:
        return cast(bool, await self.delete(user_id, meeting_id))


async def _fake_db_session() -> AsyncIterator[object]:
    yield _FakeSession()


@pytest.fixture(autouse=True)
def _secure_off(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    settings = Settings(
        upload_dir=tmp_path / "uploads",
        enable_security=False,
        auth_token_secret_key=None,
        database_url="postgresql+asyncpg://test",
        summary_enabled=True,
    )
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_db_session] = _fake_db_session
    yield
    app.dependency_overrides.clear()


def _stored() -> StoredTranscript:
    return StoredTranscript(
        user_id=TEST_USER_ID,
        id=TRANSCRIPT_ID,
        meeting_id=MEETING_ID,
        raw_text="שלום עולם. זה תמלול לדוגמה.",
        diarized_segments=[],
        language="he",
        created_at=datetime.now(UTC),
    )


def test_get_meeting_transcript_returns_probe(monkeypatch: pytest.MonkeyPatch) -> None:
    import transcripts.router as mod

    repo = _FakeTranscriptRepo(_stored())
    monkeypatch.setattr(mod, "TranscriptRepository", lambda session: repo)
    client = TestClient(app)
    res = client.get(f"/meetings/{MEETING_ID}/transcript")
    assert res.status_code == 200
    body = res.json()
    assert body["meeting_id"] == str(MEETING_ID)
    assert body["transcript_id"] == str(TRANSCRIPT_ID)
    assert body["excerpt"]


def test_get_meeting_transcript_404_when_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    import transcripts.router as mod

    monkeypatch.setattr(mod, "TranscriptRepository", lambda session: _FakeTranscriptRepo(None))
    client = TestClient(app)
    res = client.get(f"/meetings/{MEETING_ID}/transcript")
    assert res.status_code == 404


def test_delete_meeting_transcript_clears_transcript_and_summary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import transcripts.router as mod

    t_repo = _FakeTranscriptRepo(_stored())
    s_repo = _FakeSummaryRepo(deleted=True)
    monkeypatch.setattr(mod, "TranscriptRepository", lambda session: t_repo)
    monkeypatch.setattr(mod, "SummaryRepository", lambda session: s_repo)
    client = TestClient(app)
    res = client.delete(f"/meetings/{MEETING_ID}/transcript")
    assert res.status_code == 204
    t_repo.delete.assert_awaited()
    s_repo.delete.assert_awaited()


def test_delete_meeting_transcript_404_when_nothing_to_clear(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import transcripts.router as mod

    t_repo = _FakeTranscriptRepo(None)
    t_repo.delete = AsyncMock(return_value=False)
    s_repo = _FakeSummaryRepo(deleted=False)
    monkeypatch.setattr(mod, "TranscriptRepository", lambda session: t_repo)
    monkeypatch.setattr(mod, "SummaryRepository", lambda session: s_repo)
    client = TestClient(app)
    res = client.delete(f"/meetings/{MEETING_ID}/transcript")
    assert res.status_code == 404
