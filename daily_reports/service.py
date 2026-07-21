import asyncio
import logging
import uuid
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from calendar_events.models import CalendarEvent
from calendar_events.repository import CalendarEventRepository
from core.config import Settings
from core.database import get_sessionmaker
from daily_reports.models import (
    DailyMeetingContext,
    DailyReportFailedError,
    StoredDailyReport,
)
from daily_reports.prompt import DAILY_REPORT_PROMPT_VERSION
from daily_reports.repository import DailyMeetingReportRepository
from daily_reports.synthesizer import DailyReportSynthesizer, OllamaDailyReportSynthesizer
from patients.repository import PatientRepository
from reports.models import StoredReport
from reports.repository import NextMeetingReportRepository
from reports.service import NO_READY_SUMMARIES_ERROR, NextMeetingReportService, build_synthesizer
from summaries.repository import SummaryRepository

logger = logging.getLogger(__name__)

NO_DAILY_MEETINGS_TEXT = "לא מתוכננות פגישות עם מטופלים ליום זה."
INTERRUPTED_DAILY_REPORT_ERROR = "generation was interrupted by a server restart"
DEFAULT_MEETING_REPORT_POLL_INTERVAL_SECONDS = 1.0
MEETING_REPORT_WAIT_GRACE_SECONDS = 30.0


def build_daily_synthesizer(settings: Settings) -> DailyReportSynthesizer:
    from ollama import AsyncClient

    return OllamaDailyReportSynthesizer(
        client=AsyncClient(host=settings.ollama_host, timeout=settings.ollama_timeout_seconds),
        model=settings.ollama_model,
        num_ctx=settings.ollama_num_ctx,
    )


def build_daily_report_service(
    *,
    reports: DailyMeetingReportRepository,
    calendar: CalendarEventRepository,
    patients: PatientRepository,
    meeting_reports: NextMeetingReportService,
    synthesizer: DailyReportSynthesizer,
    meeting_report_wait_timeout_seconds: float = 630.0,
    meeting_report_poll_interval_seconds: float = DEFAULT_MEETING_REPORT_POLL_INTERVAL_SECONDS,
) -> "DailyMeetingReportService":
    return DailyMeetingReportService(
        reports=reports,
        calendar=calendar,
        patients=patients,
        meeting_reports=meeting_reports,
        synthesizer=synthesizer,
        meeting_report_wait_timeout_seconds=meeting_report_wait_timeout_seconds,
        meeting_report_poll_interval_seconds=meeting_report_poll_interval_seconds,
    )


async def sweep_interrupted_daily_reports(settings: Settings) -> None:
    if not settings.database_url or not settings.summary_enabled:
        return
    sessionmaker = get_sessionmaker(settings.database_url)
    async with sessionmaker() as session:
        await fail_interrupted_daily_reports(DailyMeetingReportRepository(session))


async def fail_interrupted_daily_reports(reports: DailyMeetingReportRepository) -> int:
    stranded = await reports.list_running()
    for report in stranded:
        await reports.mark_failed(
            report.user_id,
            report.id,
            error=INTERRUPTED_DAILY_REPORT_ERROR,
        )
    if stranded:
        logger.warning("failed %d daily reports interrupted by restart", len(stranded))
    return len(stranded)


async def run_daily_report_generation(
    user_id: uuid.UUID,
    report_id: uuid.UUID,
    settings: Settings,
) -> None:
    """Background entrypoint using its own session after the request has ended."""
    if not settings.database_url:
        return
    sessionmaker = get_sessionmaker(settings.database_url)
    async with sessionmaker() as session:
        meeting_reports = NextMeetingReportService(
            reports=NextMeetingReportRepository(session),
            summaries=SummaryRepository(session),
            calendar=CalendarEventRepository(session),
            synthesizer=build_synthesizer(settings),
        )
        service = build_daily_report_service(
            reports=DailyMeetingReportRepository(session),
            calendar=CalendarEventRepository(session),
            patients=PatientRepository(session),
            meeting_reports=meeting_reports,
            synthesizer=build_daily_synthesizer(settings),
            meeting_report_wait_timeout_seconds=(
                settings.ollama_timeout_seconds + MEETING_REPORT_WAIT_GRACE_SECONDS
            ),
        )
        await service.generate(user_id, report_id)


class DailyMeetingReportService:
    """Orchestrates meeting prep reports into one short daily spoken brief."""

    def __init__(
        self,
        *,
        reports: DailyMeetingReportRepository,
        calendar: CalendarEventRepository,
        patients: PatientRepository,
        meeting_reports: NextMeetingReportService,
        synthesizer: DailyReportSynthesizer,
        meeting_report_wait_timeout_seconds: float = 630.0,
        meeting_report_poll_interval_seconds: float = DEFAULT_MEETING_REPORT_POLL_INTERVAL_SECONDS,
    ) -> None:
        self._reports = reports
        self._calendar = calendar
        self._patients = patients
        self._meeting_reports = meeting_reports
        self._synthesizer = synthesizer
        self._meeting_report_wait_timeout_seconds = meeting_report_wait_timeout_seconds
        self._meeting_report_poll_interval_seconds = meeting_report_poll_interval_seconds

    async def request_report(
        self,
        user_id: uuid.UUID,
        report_date: date,
        *,
        time_zone: str,
        meeting_limit: int,
        refresh: bool,
    ) -> tuple[StoredDailyReport, bool]:
        existing = await self._reports.get_by_date(user_id, report_date)
        if existing is not None and (existing.status in ("pending", "running") or not refresh):
            return existing, False
        report = await self._reports.create_pending(
            user_id,
            report_date,
            time_zone=time_zone,
            meeting_limit=meeting_limit,
        )
        return report, True

    async def get(
        self,
        user_id: uuid.UUID,
        report_id: uuid.UUID,
    ) -> StoredDailyReport | None:
        return await self._reports.get_by_id(user_id, report_id)

    @staticmethod
    def _day_bounds(report_date: date, time_zone: ZoneInfo) -> tuple[datetime, datetime]:
        local_start = datetime.combine(report_date, time.min, tzinfo=time_zone)
        local_end = datetime.combine(report_date + timedelta(days=1), time.min, tzinfo=time_zone)
        return local_start.astimezone(UTC), local_end.astimezone(UTC)

    async def _ensure_meeting_report(
        self,
        user_id: uuid.UUID,
        meeting: CalendarEvent,
    ) -> StoredReport:
        assert meeting.patient_id is not None
        report = await self._meeting_reports.get(user_id, meeting.id)
        if report is not None and report.status in ("pending", "running"):
            return await self._wait_for_meeting_report(user_id, meeting.id)
        if report is None or report.status == "failed":
            await self._meeting_reports.create_pending(
                user_id,
                meeting.patient_id,
                meeting.id,
            )
        if report is None or report.status != "ready":
            await self._meeting_reports.generate(user_id, meeting.patient_id, meeting.id)
            report = await self._meeting_reports.get(user_id, meeting.id)
        if report is None or report.status in ("pending", "running"):
            raise DailyReportFailedError(
                f"meeting report {meeting.id} did not reach a terminal state"
            )
        if report.status == "failed" and report.error != NO_READY_SUMMARIES_ERROR:
            raise DailyReportFailedError(
                f"meeting report {meeting.id} failed: {report.error or 'unknown error'}"
            )
        return report

    async def _wait_for_meeting_report(
        self,
        user_id: uuid.UUID,
        meeting_id: uuid.UUID,
    ) -> StoredReport:
        loop = asyncio.get_running_loop()
        deadline = loop.time() + self._meeting_report_wait_timeout_seconds

        while True:
            report = await self._meeting_reports.get_fresh(user_id, meeting_id)
            if report is None:
                raise DailyReportFailedError(f"meeting report {meeting_id} disappeared")
            if report.status in ("ready", "failed"):
                if report.status == "failed" and report.error != NO_READY_SUMMARIES_ERROR:
                    raise DailyReportFailedError(
                        f"meeting report {meeting_id} failed: {report.error or 'unknown error'}"
                    )
                return report

            remaining = deadline - loop.time()
            if remaining <= 0:
                raise DailyReportFailedError(f"timed out waiting for meeting report {meeting_id}")
            await asyncio.sleep(min(self._meeting_report_poll_interval_seconds, remaining))

    async def generate(self, user_id: uuid.UUID, report_id: uuid.UUID) -> None:
        report = await self._reports.get_by_id(user_id, report_id)
        if report is None:
            return

        try:
            await self._reports.mark_running(user_id, report_id)
            time_zone = ZoneInfo(report.time_zone)
            from_at, to_at = self._day_bounds(report.report_date, time_zone)
            calendar_events = await self._calendar.list_all(
                user_id=user_id,
                from_at=from_at,
                to_at=to_at,
            )
            meetings = [
                event
                for event in calendar_events
                if event.patient_id is not None and from_at <= event.start_at < to_at
            ][: report.meeting_limit]

            if not meetings:
                await self._reports.mark_ready(
                    user_id,
                    report_id,
                    text=NO_DAILY_MEETINGS_TEXT,
                    meeting_count=0,
                    source_meeting_ids=[],
                    source_report_ids=[],
                    model="",
                    prompt_version=DAILY_REPORT_PROMPT_VERSION,
                )
                return

            contexts: list[DailyMeetingContext] = []
            source_report_ids: list[uuid.UUID] = []
            for meeting in meetings:
                assert meeting.patient_id is not None
                patient = await self._patients.get(user_id, meeting.patient_id)
                meeting_report = await self._ensure_meeting_report(user_id, meeting)
                source_report_ids.append(meeting_report.id)
                available = meeting_report.status == "ready"
                contexts.append(
                    DailyMeetingContext(
                        meeting_id=meeting.id,
                        patient_id=meeting.patient_id,
                        patient_name=patient.name,
                        start_at=meeting.start_at,
                        intro=meeting_report.intro if available else None,
                        changes=list(meeting_report.changes) if available else [],
                        open_topics=list(meeting_report.open_topics) if available else [],
                        context_available=available,
                    )
                )

            generated = await self._synthesizer.synthesize(
                meetings=contexts,
                time_zone=time_zone,
            )
            await self._reports.mark_ready(
                user_id,
                report_id,
                text=generated.text,
                meeting_count=len(meetings),
                source_meeting_ids=[meeting.id for meeting in meetings],
                source_report_ids=source_report_ids,
                model=generated.model,
                prompt_version=DAILY_REPORT_PROMPT_VERSION,
            )
        except Exception as exc:
            logger.error("daily meeting report generation failed", exc_info=exc)
            await self._reports.mark_failed(user_id, report_id, error=str(exc))
