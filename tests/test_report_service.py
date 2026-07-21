import uuid
from datetime import UTC, datetime

import pytest

from calendar_events.models import CalendarEvent
from reports.models import GeneratedReport, NoUpcomingMeetingError, StoredReport
from reports.service import (
    NO_READY_SUMMARIES_ERROR,
    NextMeetingReportService,
    fail_interrupted_reports,
)
from reports.synthesizer import ReportSynthesizer
from summaries.models import ReadyMeetingSummary

PATIENT_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")
MEETING_A = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
MEETING_B = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
MEETING_TARGET = uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
USER_ID = uuid.UUID("11111111-2222-3333-4444-555555555555")


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

    def _row(
        self,
        user_id: uuid.UUID,
        meeting_id: uuid.UUID,
        patient_id: uuid.UUID,
        **changes: object,
    ) -> StoredReport:
        now = datetime.now(UTC)
        current = self.rows.get(meeting_id)
        base: dict[str, object] = {
            "user_id": user_id,
            "id": current.id if current else uuid.uuid4(),
            "patient_id": patient_id,
            "meeting_id": meeting_id,
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
        self.rows[meeting_id] = row
        self.transitions.append(row.status)
        return row

    async def create_pending(
        self,
        user_id: uuid.UUID,
        patient_id: uuid.UUID,
        meeting_id: uuid.UUID,
        *,
        model: str = "",
    ) -> StoredReport:
        return self._row(
            user_id,
            meeting_id,
            patient_id,
            status="pending",
            model=model,
            intro=None,
            error=None,
        )

    async def mark_running(self, user_id: uuid.UUID, meeting_id: uuid.UUID) -> StoredReport:
        row = self.rows[meeting_id]
        return self._row(user_id, meeting_id, row.patient_id, status="running")

    async def mark_ready(
        self,
        user_id: uuid.UUID,
        meeting_id: uuid.UUID,
        *,
        intro: str,
        changes: list[str],
        open_topics: list[str],
        source_meeting_ids: list[uuid.UUID],
        model: str,
    ) -> StoredReport:
        row = self.rows[meeting_id]
        return self._row(
            user_id,
            meeting_id,
            row.patient_id,
            status="ready",
            intro=intro,
            changes=changes,
            open_topics=open_topics,
            source_meeting_ids=source_meeting_ids,
            model=model,
            error=None,
        )

    async def mark_failed(
        self,
        user_id: uuid.UUID,
        meeting_id: uuid.UUID,
        *,
        error: str,
    ) -> StoredReport:
        row = self.rows[meeting_id]
        return self._row(user_id, meeting_id, row.patient_id, status="failed", error=error)

    async def get_by_meeting_id(
        self,
        user_id: uuid.UUID,
        meeting_id: uuid.UUID,
    ) -> StoredReport | None:
        return self.rows.get(meeting_id)

    async def list_for_patient(
        self,
        user_id: uuid.UUID,
        patient_id: uuid.UUID,
    ) -> list[StoredReport]:
        return [
            row
            for row in self.rows.values()
            if row.user_id == user_id and row.patient_id == patient_id
        ]

    async def list_running(self) -> list[StoredReport]:
        return [row for row in self.rows.values() if row.status == "running"]


class _FakeSummaryRepository:
    def __init__(self, ready: list[ReadyMeetingSummary]) -> None:
        self._ready = ready

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


class _FakeCalendarRepository:
    def __init__(self, meeting: CalendarEvent) -> None:
        self._meeting = meeting

    async def get_meeting(self, user_id: uuid.UUID, meeting_id: uuid.UUID) -> CalendarEvent:
        if user_id != self._meeting.user_id or meeting_id != self._meeting.id:
            from calendar_events.models import CalendarEventNotFoundError

            raise CalendarEventNotFoundError(meeting_id)
        return self._meeting

    async def get(self, user_id: uuid.UUID, meeting_id: uuid.UUID) -> CalendarEvent:
        return await self.get_meeting(user_id, meeting_id)

    async def find_active_meeting_for_patient(
        self,
        user_id: uuid.UUID,
        patient_id: uuid.UUID,
        *,
        now: datetime,
    ) -> CalendarEvent | None:
        if user_id != self._meeting.user_id or patient_id != self._meeting.patient_id:
            return None
        if self._meeting.end_at <= now:
            return None
        return self._meeting

    async def find_latest_meeting_for_patient(
        self,
        user_id: uuid.UUID,
        patient_id: uuid.UUID,
    ) -> CalendarEvent | None:
        if user_id != self._meeting.user_id or patient_id != self._meeting.patient_id:
            return None
        return self._meeting


def _target_meeting(*, start_at: datetime | None = None) -> CalendarEvent:
    start = start_at or datetime(2026, 7, 20, 10, 0, tzinfo=UTC)
    end = start.replace(hour=start.hour + 1)
    return CalendarEvent(
        id=MEETING_TARGET,
        title="פגישה",
        description=None,
        start_at=start,
        end_at=end,
        created_at=datetime(2026, 7, 1, tzinfo=UTC),
        user_id=USER_ID,
        patient_id=PATIENT_ID,
    )


def _service(
    *,
    ready: list[ReadyMeetingSummary],
    synthesizer: ReportSynthesizer,
    reports: _FakeReportRepository | None = None,
    meeting: CalendarEvent | None = None,
) -> tuple[NextMeetingReportService, _FakeReportRepository, _FakeSynthesizer | ReportSynthesizer]:
    repo = reports or _FakeReportRepository()
    target = meeting or _target_meeting()
    service = NextMeetingReportService(
        reports=repo,  # type: ignore[arg-type]
        summaries=_FakeSummaryRepository(ready),  # type: ignore[arg-type]
        calendar=_FakeCalendarRepository(target),  # type: ignore[arg-type]
        synthesizer=synthesizer,
    )
    return service, repo, synthesizer


def _ready(meeting_id: uuid.UUID, *, days_ago: int, text: str) -> ReadyMeetingSummary:
    start = datetime(2026, 7, 20, tzinfo=UTC).replace(day=max(1, 20 - days_ago))
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
    await repo.create_pending(USER_ID, PATIENT_ID, MEETING_TARGET)

    await service.generate(USER_ID, PATIENT_ID, MEETING_TARGET)

    row = repo.rows[MEETING_TARGET]
    assert row.status == "ready"
    assert row.intro == "סקירה"
    assert row.changes == ["שינוי א"]
    assert row.open_topics == ["נושא א"]
    assert row.source_meeting_ids == [MEETING_A, MEETING_B]
    assert [s.meeting_id for s in synth.calls[0]] == [MEETING_A, MEETING_B]


@pytest.mark.anyio
async def test_generate_excludes_target_and_future_summaries() -> None:
    synth = _FakeSynthesizer()
    future = ReadyMeetingSummary(
        meeting_id=uuid.uuid4(),
        start_at=datetime(2026, 7, 25, 10, 0, tzinfo=UTC),
        text="עתידי",
    )
    service, repo, _ = _service(
        ready=[
            _ready(MEETING_B, days_ago=1, text="עבר"),
            future,
        ],
        synthesizer=synth,
    )
    await repo.create_pending(USER_ID, PATIENT_ID, MEETING_TARGET)

    await service.generate(USER_ID, PATIENT_ID, MEETING_TARGET)

    assert [s.meeting_id for s in synth.calls[0]] == [MEETING_B]


@pytest.mark.anyio
async def test_generate_with_no_ready_summaries_fails_in_hebrew() -> None:
    service, repo, synth = _service(ready=[], synthesizer=_FakeSynthesizer())
    await repo.create_pending(USER_ID, PATIENT_ID, MEETING_TARGET)

    await service.generate(USER_ID, PATIENT_ID, MEETING_TARGET)

    row = repo.rows[MEETING_TARGET]
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
    await repo.create_pending(USER_ID, PATIENT_ID, MEETING_TARGET)

    await service.generate(USER_ID, PATIENT_ID, MEETING_TARGET)

    row = repo.rows[MEETING_TARGET]
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
    await repo.create_pending(USER_ID, PATIENT_ID, MEETING_TARGET)

    await service.generate(USER_ID, PATIENT_ID, MEETING_TARGET)

    row = repo.rows[MEETING_TARGET]
    assert row.status == "ready"
    assert row.open_topics == ["לחזור לדפוסי שינה", "לחזק ויסות"]


@pytest.mark.anyio
async def test_regenerating_second_meeting_preserves_first_report() -> None:
    repo = _FakeReportRepository()
    other_meeting = uuid.UUID("dddddddd-dddd-dddd-dddd-dddddddddddd")
    await repo.create_pending(USER_ID, PATIENT_ID, MEETING_TARGET)
    await repo.mark_ready(
        USER_ID,
        MEETING_TARGET,
        intro="ישן",
        changes=["א"],
        open_topics=["ב"],
        source_meeting_ids=[MEETING_A],
        model="m",
    )
    await repo.create_pending(USER_ID, PATIENT_ID, other_meeting)

    assert repo.rows[MEETING_TARGET].intro == "ישן"
    assert repo.rows[other_meeting].status == "pending"


@pytest.mark.anyio
async def test_fail_interrupted_reports_sweeps_running_rows() -> None:
    reports = _FakeReportRepository()
    await reports.create_pending(USER_ID, PATIENT_ID, MEETING_TARGET)
    await reports.mark_running(USER_ID, MEETING_TARGET)

    count = await fail_interrupted_reports(reports)  # type: ignore[arg-type]

    assert count == 1
    assert reports.rows[MEETING_TARGET].status == "failed"


@pytest.mark.anyio
async def test_resolve_next_meeting_falls_back_to_latest_when_none_upcoming() -> None:
    # A past-only meeting: no active/upcoming one, so the resolver uses the most
    # recent meeting instead of failing — a brief can still be requested.
    past = _target_meeting(start_at=datetime(2026, 6, 1, 10, 0, tzinfo=UTC))
    service, _, _ = _service(ready=[], synthesizer=_FakeSynthesizer(), meeting=past)

    resolved = await service.resolve_next_meeting(USER_ID, PATIENT_ID)

    assert resolved.id == past.id


@pytest.mark.anyio
async def test_resolve_next_meeting_raises_when_patient_has_no_meetings() -> None:
    service, _, _ = _service(ready=[], synthesizer=_FakeSynthesizer())

    with pytest.raises(NoUpcomingMeetingError):
        await service.resolve_next_meeting(USER_ID, uuid.uuid4())
