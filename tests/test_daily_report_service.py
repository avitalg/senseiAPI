import uuid
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from calendar_events.models import CalendarEvent
from daily_reports.models import (
    DailyMeetingContext,
    DailyReportStatus,
    GeneratedDailyReport,
    StoredDailyReport,
)
from daily_reports.service import (
    INTERRUPTED_DAILY_REPORT_ERROR,
    NO_DAILY_MEETINGS_TEXT,
    DailyMeetingReportService,
    fail_interrupted_daily_reports,
)
from daily_reports.synthesizer import DailyReportSynthesizer
from patients.models import Patient
from reports.models import ReportStatus, StoredReport
from reports.service import NO_READY_SUMMARIES_ERROR

USER_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
PATIENT_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")
REPORT_ID = uuid.UUID("33333333-3333-3333-3333-333333333333")
REPORT_DATE = date(2026, 7, 21)
NOW = datetime(2026, 7, 21, 5, 0, tzinfo=UTC)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def _daily(status: DailyReportStatus = "pending", **changes: object) -> StoredDailyReport:
    base: dict[str, object] = {
        "user_id": USER_ID,
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


def _meeting(
    index: int,
    *,
    patient_id: uuid.UUID | None = PATIENT_ID,
    start_at: datetime | None = None,
) -> CalendarEvent:
    meeting_id = uuid.UUID(f"aaaaaaaa-aaaa-aaaa-aaaa-{index:012d}")
    start = start_at or datetime(2026, 7, 21, 6 + index, 0, tzinfo=UTC)
    return CalendarEvent(
        id=meeting_id,
        title="פגישה",
        description=None,
        start_at=start,
        end_at=start + timedelta(hours=1),
        created_at=NOW,
        user_id=USER_ID,
        patient_id=patient_id,
    )


def _meeting_report(
    meeting: CalendarEvent,
    status: ReportStatus = "ready",
    *,
    error: str | None = None,
) -> StoredReport:
    assert meeting.patient_id is not None
    return StoredReport(
        user_id=USER_ID,
        id=uuid.uuid5(uuid.NAMESPACE_URL, str(meeting.id)),
        patient_id=meeting.patient_id,
        meeting_id=meeting.id,
        status=status,
        intro="סקירה",
        changes=["שינוי"],
        open_topics=["נושא פתוח"],
        source_meeting_ids=[uuid.uuid4()],
        model="meeting-model",
        error=error,
        created_at=NOW,
        updated_at=NOW,
    )


class _FakeDailyRepository:
    def __init__(self, report: StoredDailyReport | None = None) -> None:
        self.report = report

    async def get_by_date(
        self,
        user_id: uuid.UUID,
        report_date: date,
    ) -> StoredDailyReport | None:
        if (
            self.report
            and self.report.user_id == user_id
            and self.report.report_date == report_date
        ):
            return self.report
        return None

    async def get_by_id(
        self,
        user_id: uuid.UUID,
        report_id: uuid.UUID,
    ) -> StoredDailyReport | None:
        if self.report and self.report.user_id == user_id and self.report.id == report_id:
            return self.report
        return None

    async def create_pending(
        self,
        user_id: uuid.UUID,
        report_date: date,
        *,
        time_zone: str,
        meeting_limit: int,
    ) -> StoredDailyReport:
        current = self.report or _daily()
        self.report = replace(
            current,
            report_date=report_date,
            time_zone=time_zone,
            status="pending",
            meeting_limit=meeting_limit,
            meeting_count=0,
            text=None,
            source_meeting_ids=[],
            source_report_ids=[],
            model="",
            prompt_version="",
            error=None,
        )
        return self.report

    async def mark_running(
        self,
        user_id: uuid.UUID,
        report_id: uuid.UUID,
    ) -> StoredDailyReport:
        assert self.report is not None
        self.report = replace(self.report, status="running")
        return self.report

    async def mark_ready(
        self,
        user_id: uuid.UUID,
        report_id: uuid.UUID,
        *,
        text: str,
        meeting_count: int,
        source_meeting_ids: list[uuid.UUID],
        source_report_ids: list[uuid.UUID],
        model: str,
        prompt_version: str,
    ) -> StoredDailyReport:
        assert self.report is not None
        self.report = replace(
            self.report,
            status="ready",
            text=text,
            meeting_count=meeting_count,
            source_meeting_ids=list(source_meeting_ids),
            source_report_ids=list(source_report_ids),
            model=model,
            prompt_version=prompt_version,
            error=None,
        )
        return self.report

    async def mark_failed(
        self,
        user_id: uuid.UUID,
        report_id: uuid.UUID,
        *,
        error: str,
    ) -> StoredDailyReport:
        assert self.report is not None
        self.report = replace(self.report, status="failed", error=error)
        return self.report

    async def list_running(self) -> list[StoredDailyReport]:
        if self.report is not None and self.report.status == "running":
            return [self.report]
        return []


class _FakeCalendarRepository:
    def __init__(self, meetings: list[CalendarEvent]) -> None:
        self.meetings = meetings
        self.bounds: tuple[datetime, datetime] | None = None

    async def list_all(
        self,
        *,
        user_id: uuid.UUID,
        from_at: datetime,
        to_at: datetime,
    ) -> list[CalendarEvent]:
        self.bounds = (from_at, to_at)
        return self.meetings


class _FakePatients:
    async def get(self, user_id: uuid.UUID, patient_id: uuid.UUID) -> Patient:
        return Patient(
            user_id=user_id,
            id=patient_id,
            name="דנה",
            phone="050",
            email=None,
            created_at=NOW,
        )


class _FakeMeetingReports:
    def __init__(
        self,
        reports: list[StoredReport] | None = None,
        *,
        generated_status: ReportStatus = "ready",
        generated_error: str | None = None,
        fresh_statuses: list[ReportStatus] | None = None,
    ) -> None:
        self.reports = {report.meeting_id: report for report in reports or []}
        self.generated_status = generated_status
        self.generated_error = generated_error
        self.fresh_statuses = list(fresh_statuses or [])
        self.created: list[uuid.UUID] = []
        self.generated: list[uuid.UUID] = []
        self.fresh_reads: list[uuid.UUID] = []

    async def get(self, user_id: uuid.UUID, meeting_id: uuid.UUID) -> StoredReport | None:
        return self.reports.get(meeting_id)

    async def get_fresh(
        self,
        user_id: uuid.UUID,
        meeting_id: uuid.UUID,
    ) -> StoredReport | None:
        self.fresh_reads.append(meeting_id)
        report = self.reports.get(meeting_id)
        if report is not None and self.fresh_statuses:
            status = self.fresh_statuses.pop(0)
            report = replace(
                report,
                status=status,
                error=None if status == "ready" else report.error,
            )
            self.reports[meeting_id] = report
        return report

    async def create_pending(
        self,
        user_id: uuid.UUID,
        patient_id: uuid.UUID,
        meeting_id: uuid.UUID,
    ) -> StoredReport:
        meeting = _meeting(0, patient_id=patient_id)
        meeting = replace(meeting, id=meeting_id)
        report = _meeting_report(meeting, "pending")
        self.reports[meeting_id] = report
        self.created.append(meeting_id)
        return report

    async def generate(
        self,
        user_id: uuid.UUID,
        patient_id: uuid.UUID,
        meeting_id: uuid.UUID,
    ) -> None:
        current = self.reports[meeting_id]
        self.reports[meeting_id] = replace(
            current,
            status=self.generated_status,
            error=self.generated_error,
        )
        self.generated.append(meeting_id)


class _FakeSynthesizer(DailyReportSynthesizer):
    def __init__(self, *, error: Exception | None = None) -> None:
        self.error = error
        self.calls: list[list[DailyMeetingContext]] = []
        self.time_zones: list[ZoneInfo] = []

    async def synthesize(
        self,
        *,
        meetings: list[DailyMeetingContext],  # type: ignore[override]
        time_zone: ZoneInfo,
    ) -> GeneratedDailyReport:
        self.calls.append(list(meetings))
        self.time_zones.append(time_zone)
        if self.error is not None:
            raise self.error
        return GeneratedDailyReport(
            text="תדריך יומי קצר.",
            model="daily-model",
            raw_text='{ "text": "תדריך יומי קצר." }',
        )


def _service(
    *,
    daily: _FakeDailyRepository,
    meetings: list[CalendarEvent],
    meeting_reports: _FakeMeetingReports | None = None,
    synthesizer: _FakeSynthesizer | None = None,
    wait_timeout_seconds: float = 630.0,
) -> tuple[
    DailyMeetingReportService, _FakeCalendarRepository, _FakeMeetingReports, _FakeSynthesizer
]:
    calendar = _FakeCalendarRepository(meetings)
    reports = meeting_reports or _FakeMeetingReports()
    synth = synthesizer or _FakeSynthesizer()
    service = DailyMeetingReportService(
        reports=daily,  # type: ignore[arg-type]
        calendar=calendar,  # type: ignore[arg-type]
        patients=_FakePatients(),  # type: ignore[arg-type]
        meeting_reports=reports,  # type: ignore[arg-type]
        synthesizer=synth,
        meeting_report_wait_timeout_seconds=wait_timeout_seconds,
        meeting_report_poll_interval_seconds=0,
    )
    return service, calendar, reports, synth


@pytest.mark.anyio
async def test_request_reuses_existing_report_without_refresh() -> None:
    repository = _FakeDailyRepository(_daily("ready", text="ישן"))
    service, _, _, _ = _service(daily=repository, meetings=[])

    report, should_generate = await service.request_report(
        USER_ID,
        REPORT_DATE,
        time_zone="Europe/Paris",
        meeting_limit=2,
        refresh=False,
    )

    assert should_generate is False
    assert report.text == "ישן"
    assert report.time_zone == "Asia/Jerusalem"
    assert report.meeting_limit == 4


@pytest.mark.anyio
async def test_request_refreshes_existing_report_with_new_parameters() -> None:
    repository = _FakeDailyRepository(_daily("ready", text="ישן"))
    service, _, _, _ = _service(daily=repository, meetings=[])

    report, should_generate = await service.request_report(
        USER_ID,
        REPORT_DATE,
        time_zone="Europe/Paris",
        meeting_limit=2,
        refresh=True,
    )

    assert should_generate is True
    assert report.status == "pending"
    assert report.text is None
    assert report.time_zone == "Europe/Paris"
    assert report.meeting_limit == 2


@pytest.mark.anyio
async def test_request_does_not_duplicate_inflight_generation_on_refresh() -> None:
    repository = _FakeDailyRepository(_daily("running"))
    service, _, _, _ = _service(daily=repository, meetings=[])

    report, should_generate = await service.request_report(
        USER_ID,
        REPORT_DATE,
        time_zone="Asia/Jerusalem",
        meeting_limit=4,
        refresh=True,
    )

    assert report.status == "running"
    assert should_generate is False


@pytest.mark.anyio
async def test_generate_uses_first_four_calendar_events_without_deduplication() -> None:
    meetings = [_meeting(index) for index in range(5)]
    ready = [_meeting_report(meeting) for meeting in meetings]
    daily = _FakeDailyRepository(_daily())
    service, calendar, _, synth = _service(
        daily=daily,
        meetings=meetings,
        meeting_reports=_FakeMeetingReports(ready),
    )

    await service.generate(USER_ID, REPORT_ID)

    assert daily.report is not None
    assert daily.report.status == "ready"
    assert daily.report.meeting_count == 4
    assert daily.report.source_meeting_ids == [meeting.id for meeting in meetings[:4]]
    assert len(synth.calls[0]) == 4
    assert [item.patient_id for item in synth.calls[0]] == [PATIENT_ID] * 4
    assert calendar.bounds == (
        datetime(2026, 7, 20, 21, 0, tzinfo=UTC),
        datetime(2026, 7, 21, 21, 0, tzinfo=UTC),
    )


@pytest.mark.anyio
async def test_generate_prepares_missing_meeting_report_through_service() -> None:
    meeting = _meeting(1)
    daily = _FakeDailyRepository(_daily())
    service, _, meeting_reports, _ = _service(daily=daily, meetings=[meeting])

    await service.generate(USER_ID, REPORT_ID)

    assert meeting_reports.created == [meeting.id]
    assert meeting_reports.generated == [meeting.id]
    assert daily.report is not None
    assert daily.report.status == "ready"


@pytest.mark.anyio
async def test_generate_waits_for_inflight_meeting_report_without_regenerating() -> None:
    meeting = _meeting(1)
    running = _meeting_report(meeting, "running")
    daily = _FakeDailyRepository(_daily())
    meeting_reports = _FakeMeetingReports(
        [running],
        fresh_statuses=["running", "ready"],
    )
    service, _, _, synth = _service(
        daily=daily,
        meetings=[meeting],
        meeting_reports=meeting_reports,
    )

    await service.generate(USER_ID, REPORT_ID)

    assert daily.report is not None
    assert daily.report.status == "ready"
    assert meeting_reports.generated == []
    assert meeting_reports.fresh_reads == [meeting.id, meeting.id]
    assert synth.calls[0][0].context_available is True


@pytest.mark.anyio
async def test_generate_fails_when_inflight_meeting_report_times_out() -> None:
    meeting = _meeting(1)
    running = _meeting_report(meeting, "running")
    daily = _FakeDailyRepository(_daily())
    meeting_reports = _FakeMeetingReports([running], fresh_statuses=["running"])
    service, _, _, synth = _service(
        daily=daily,
        meetings=[meeting],
        meeting_reports=meeting_reports,
        wait_timeout_seconds=0,
    )

    await service.generate(USER_ID, REPORT_ID)

    assert daily.report is not None
    assert daily.report.status == "failed"
    assert "timed out waiting" in (daily.report.error or "")
    assert meeting_reports.generated == []
    assert synth.calls == []


@pytest.mark.anyio
async def test_generate_keeps_meeting_without_historical_summaries_in_daily_prompt() -> None:
    meeting = _meeting(1)
    daily = _FakeDailyRepository(_daily())
    meeting_reports = _FakeMeetingReports(
        generated_status="failed",
        generated_error=NO_READY_SUMMARIES_ERROR,
    )
    service, _, _, synth = _service(
        daily=daily,
        meetings=[meeting],
        meeting_reports=meeting_reports,
    )

    await service.generate(USER_ID, REPORT_ID)

    assert daily.report is not None
    assert daily.report.status == "ready"
    assert synth.calls[0][0].context_available is False


@pytest.mark.anyio
async def test_generate_fails_for_unexpected_meeting_report_failure() -> None:
    meeting = _meeting(1)
    daily = _FakeDailyRepository(_daily())
    meeting_reports = _FakeMeetingReports(
        generated_status="failed",
        generated_error="ollama unavailable",
    )
    service, _, _, synth = _service(
        daily=daily,
        meetings=[meeting],
        meeting_reports=meeting_reports,
    )

    await service.generate(USER_ID, REPORT_ID)

    assert daily.report is not None
    assert daily.report.status == "failed"
    assert "ollama unavailable" in (daily.report.error or "")
    assert synth.calls == []


@pytest.mark.anyio
async def test_generate_empty_day_returns_ready_tts_text_without_llm() -> None:
    daily = _FakeDailyRepository(_daily())
    service, _, _, synth = _service(
        daily=daily,
        meetings=[_meeting(1, patient_id=None)],
    )

    await service.generate(USER_ID, REPORT_ID)

    assert daily.report is not None
    assert daily.report.status == "ready"
    assert daily.report.text == NO_DAILY_MEETINGS_TEXT
    assert daily.report.meeting_count == 0
    assert synth.calls == []


@pytest.mark.anyio
async def test_generate_marks_daily_report_failed_when_synthesizer_fails() -> None:
    meeting = _meeting(1)
    daily = _FakeDailyRepository(_daily())
    synthesizer = _FakeSynthesizer(error=RuntimeError("daily model unavailable"))
    service, _, _, _ = _service(
        daily=daily,
        meetings=[meeting],
        meeting_reports=_FakeMeetingReports([_meeting_report(meeting)]),
        synthesizer=synthesizer,
    )

    await service.generate(USER_ID, REPORT_ID)

    assert daily.report is not None
    assert daily.report.status == "failed"
    assert daily.report.error == "daily model unavailable"


@pytest.mark.anyio
async def test_fail_interrupted_daily_reports_marks_running_rows_failed() -> None:
    repository = _FakeDailyRepository(_daily("running"))

    count = await fail_interrupted_daily_reports(repository)  # type: ignore[arg-type]

    assert count == 1
    assert repository.report is not None
    assert repository.report.status == "failed"
    assert repository.report.error == INTERRUPTED_DAILY_REPORT_ERROR
