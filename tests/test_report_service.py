import uuid
from datetime import UTC, datetime

import pytest

from reports.models import GeneratedReport, StoredReport
from reports.service import NO_READY_SUMMARIES_ERROR, NextMeetingReportService, fail_interrupted_reports
from reports.synthesizer import ReportSynthesizer
from summaries.models import ReadyMeetingSummary

PATIENT_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")
MEETING_A = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
MEETING_B = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class _FakeSynthesizer(ReportSynthesizer):
    def __init__(
        self,
        *,
        error: Exception | None = None,
        open_topics: list[str] | None = None,
    ) -> None:
        self.error = error
        self.open_topics = ["נושא א"] if open_topics is None else open_topics
        self.calls: list[list[ReadyMeetingSummary]] = []

    async def synthesize(self, *, summaries):  # type: ignore[no-untyped-def]
        self.calls.append(list(summaries))
        if self.error is not None:
            raise self.error
        return GeneratedReport(
            intro="סקירה",
            changes=["שינוי א"],
            open_topics=list(self.open_topics),
            model="qwen2.5:7b-instruct",
            raw_text="## סקירה מהירה\nסקירה",
        )


class _FakeReportRepository:
    def __init__(self) -> None:
        self.rows: dict[uuid.UUID, StoredReport] = {}
        self.transitions: list[str] = []

    def _row(self, patient_id: uuid.UUID, **changes: object) -> StoredReport:
        now = datetime.now(UTC)
        current = self.rows.get(patient_id)
        base: dict[str, object] = {
            "id": current.id if current else uuid.uuid4(),
            "patient_id": patient_id,
            "status": "pending",
            "intro": None,
            "changes": [],
            "open_topics": [],
            "source_meeting_ids": [],
            "model": "",
            "error": None,
            "created_at": current.created_at if current else now,
            "updated_at": now,
        }
        base.update(changes)
        row = StoredReport(**base)  # type: ignore[arg-type]
        self.rows[patient_id] = row
        self.transitions.append(row.status)
        return row

    async def create_pending(self, patient_id: uuid.UUID, *, model: str = "") -> StoredReport:
        return self._row(patient_id, status="pending", model=model, intro=None, error=None)

    async def mark_running(self, patient_id: uuid.UUID) -> StoredReport:
        return self._row(patient_id, status="running")

    async def mark_ready(
        self,
        patient_id: uuid.UUID,
        *,
        intro: str,
        changes: list[str],
        open_topics: list[str],
        source_meeting_ids: list[uuid.UUID],
        model: str,
    ) -> StoredReport:
        return self._row(
            patient_id,
            status="ready",
            intro=intro,
            changes=changes,
            open_topics=open_topics,
            source_meeting_ids=source_meeting_ids,
            model=model,
            error=None,
        )

    async def mark_failed(self, patient_id: uuid.UUID, *, error: str) -> StoredReport:
        return self._row(patient_id, status="failed", error=error)

    async def get_by_patient_id(self, patient_id: uuid.UUID) -> StoredReport | None:
        return self.rows.get(patient_id)

    async def list_running(self) -> list[StoredReport]:
        return [row for row in self.rows.values() if row.status == "running"]


class _FakeSummaryRepository:
    def __init__(self, ready: list[ReadyMeetingSummary]) -> None:
        self._ready = ready

    async def list_ready_for_patient(
        self,
        patient_id: uuid.UUID,
        *,
        limit: int = 8,
    ) -> list[ReadyMeetingSummary]:
        return self._ready[:limit]


def _service(
    *,
    ready: list[ReadyMeetingSummary],
    synthesizer: ReportSynthesizer,
    reports: _FakeReportRepository | None = None,
) -> tuple[NextMeetingReportService, _FakeReportRepository, _FakeSynthesizer | ReportSynthesizer]:
    repo = reports or _FakeReportRepository()
    service = NextMeetingReportService(
        reports=repo,  # type: ignore[arg-type]
        summaries=_FakeSummaryRepository(ready),  # type: ignore[arg-type]
        synthesizer=synthesizer,
    )
    return service, repo, synthesizer


def _ready(meeting_id: uuid.UUID, *, days_ago: int, text: str) -> ReadyMeetingSummary:
    start = datetime(2026, 7, 1, tzinfo=UTC).replace(day=max(1, 10 - days_ago))
    return ReadyMeetingSummary(meeting_id=meeting_id, start_at=start, text=text)


@pytest.mark.anyio
async def test_generate_marks_ready_with_parsed_sections() -> None:
    synth = _FakeSynthesizer()
    service, repo, _ = _service(
        ready=[
            _ready(MEETING_B, days_ago=1, text="פגישה חדשה"),
            _ready(MEETING_A, days_ago=7, text="פגישה ישנה"),
        ],
        synthesizer=synth,
    )
    await repo.create_pending(PATIENT_ID)

    await service.generate(PATIENT_ID)

    row = repo.rows[PATIENT_ID]
    assert row.status == "ready"
    assert row.intro == "סקירה"
    assert row.changes == ["שינוי א"]
    assert row.open_topics == ["נושא א"]
    assert row.source_meeting_ids == [MEETING_A, MEETING_B]
    # synthesizer sees chronological order (older first)
    assert [s.meeting_id for s in synth.calls[0]] == [MEETING_A, MEETING_B]


@pytest.mark.anyio
async def test_generate_with_no_ready_summaries_fails_in_hebrew() -> None:
    service, repo, synth = _service(ready=[], synthesizer=_FakeSynthesizer())
    await repo.create_pending(PATIENT_ID)

    await service.generate(PATIENT_ID)

    row = repo.rows[PATIENT_ID]
    assert row.status == "failed"
    assert row.error == NO_READY_SUMMARIES_ERROR
    assert isinstance(synth, _FakeSynthesizer)
    assert synth.calls == []


@pytest.mark.anyio
async def test_generate_marks_failed_when_synthesizer_errors() -> None:
    service, repo, _ = _service(
        ready=[_ready(MEETING_A, days_ago=1, text="טקסט")],
        synthesizer=_FakeSynthesizer(error=RuntimeError("ollama down")),
    )
    await repo.create_pending(PATIENT_ID)

    await service.generate(PATIENT_ID)

    row = repo.rows[PATIENT_ID]
    assert row.status == "failed"
    assert "ollama down" in (row.error or "")


@pytest.mark.anyio
async def test_generate_fills_open_topics_from_last_summary_followup() -> None:
    newest = """\
## נושאים מרכזיים
חרדה.

## המשך ומעקב
- לחזור לדפוסי שינה
- לחזק ויסות
"""
    service, repo, _ = _service(
        ready=[
            _ready(MEETING_B, days_ago=1, text=newest),
            _ready(MEETING_A, days_ago=7, text="ישן"),
        ],
        synthesizer=_FakeSynthesizer(open_topics=[]),
    )
    await repo.create_pending(PATIENT_ID)

    await service.generate(PATIENT_ID)

    row = repo.rows[PATIENT_ID]
    assert row.status == "ready"
    assert row.open_topics == ["לחזור לדפוסי שינה", "לחזק ויסות"]


@pytest.mark.anyio
async def test_fail_interrupted_reports_sweeps_running_rows() -> None:
    reports = _FakeReportRepository()
    await reports.mark_running(PATIENT_ID)

    count = await fail_interrupted_reports(reports)  # type: ignore[arg-type]

    assert count == 1
    assert reports.rows[PATIENT_ID].status == "failed"
