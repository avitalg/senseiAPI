import logging
import uuid
from datetime import UTC, datetime

from calendar_events.models import CalendarEvent, CalendarEventNotFoundError
from calendar_events.repository import CalendarEventRepository
from core.config import Settings
from core.database import get_sessionmaker
from reports.models import (
    MeetingPatientMismatchError,
    NoUpcomingMeetingError,
    StoredReport,
)
from reports.parse import FOLLOWUP_HEADING, bullets_under_heading
from reports.repository import NextMeetingReportRepository
from reports.synthesizer import OllamaReportSynthesizer, OpenAIReportSynthesizer, ReportSynthesizer
from summaries.repository import SummaryRepository

logger = logging.getLogger(__name__)

NO_READY_SUMMARIES_ERROR = "אין סיכומי פגישות מוכנים"


def build_synthesizer(settings: Settings) -> ReportSynthesizer:
    """Build the configured report synthesizer (same SUMMARY_BACKEND as summaries)."""
    if settings.summary_backend == "openai":
        if not settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is required when SUMMARY_BACKEND=openai")
        # Imported lazily so the SDK is only needed when this backend is selected.
        from openai import AsyncOpenAI

        return OpenAIReportSynthesizer(
            client=AsyncOpenAI(api_key=settings.openai_api_key),
            model=settings.openai_model,
        )

    from ollama import AsyncClient

    return OllamaReportSynthesizer(
        client=AsyncClient(host=settings.ollama_host, timeout=settings.ollama_timeout_seconds),
        model=settings.ollama_model,
        num_ctx=settings.ollama_num_ctx,
    )


async def sweep_interrupted_reports(settings: Settings) -> None:
    if not settings.database_url or not settings.summary_enabled:
        return

    sessionmaker = get_sessionmaker(settings.database_url)
    async with sessionmaker() as session:
        await fail_interrupted_reports(NextMeetingReportRepository(session))


async def fail_interrupted_reports(reports: NextMeetingReportRepository) -> int:
    stranded = await reports.list_running()
    for report in stranded:
        await reports.mark_failed(
            report.user_id,
            report.meeting_id,
            error="generation was interrupted by a server restart",
        )
    if stranded:
        logger.warning("failed %d next-meeting reports interrupted by restart", len(stranded))
    return len(stranded)


async def run_report_generation(
    user_id: uuid.UUID,
    patient_id: uuid.UUID,
    meeting_id: uuid.UUID,
    settings: Settings,
) -> None:
    """Background entrypoint — opens its own session (request session is closed)."""
    if not settings.database_url:
        return
    sessionmaker = get_sessionmaker(settings.database_url)
    async with sessionmaker() as session:
        service = NextMeetingReportService(
            reports=NextMeetingReportRepository(session),
            summaries=SummaryRepository(session),
            calendar=CalendarEventRepository(session),
            synthesizer=build_synthesizer(settings),
        )
        await service.generate(user_id, patient_id, meeting_id)


class NextMeetingReportService:
    """Builds a cross-meeting prep brief from ready per-meeting summaries."""

    def __init__(
        self,
        *,
        reports: NextMeetingReportRepository,
        summaries: SummaryRepository,
        calendar: CalendarEventRepository,
        synthesizer: ReportSynthesizer,
        summary_limit: int = 8,
        now: datetime | None = None,
    ) -> None:
        self._reports = reports
        self._summaries = summaries
        self._calendar = calendar
        self._synthesizer = synthesizer
        self._summary_limit = summary_limit
        self._now = now

    def _current_time(self) -> datetime:
        return self._now if self._now is not None else datetime.now(UTC)

    async def resolve_next_meeting(
        self,
        user_id: uuid.UUID,
        patient_id: uuid.UUID,
    ) -> CalendarEvent:
        # Prefer an in-progress/upcoming meeting — the brief is prep for the next session.
        meeting = await self._calendar.find_active_meeting_for_patient(
            user_id,
            patient_id,
            now=self._current_time(),
        )
        if meeting is None:
            # No upcoming meeting: fall back to the most recent one so a history-based
            # brief can still be produced on demand. Only fail if the patient has none.
            meeting = await self._calendar.find_latest_meeting_for_patient(user_id, patient_id)
        if meeting is None:
            raise NoUpcomingMeetingError(patient_id)
        return meeting

    async def verify_meeting_for_patient(
        self,
        user_id: uuid.UUID,
        patient_id: uuid.UUID,
        meeting_id: uuid.UUID,
    ) -> CalendarEvent:
        try:
            meeting = await self._calendar.get_meeting(user_id, meeting_id)
        except CalendarEventNotFoundError as exc:
            raise exc
        if meeting.patient_id != patient_id:
            raise MeetingPatientMismatchError(patient_id, meeting_id)
        return meeting

    async def create_pending(
        self,
        user_id: uuid.UUID,
        patient_id: uuid.UUID,
        meeting_id: uuid.UUID,
    ) -> StoredReport:
        existing = await self._reports.get_by_meeting_id(user_id, meeting_id)
        if existing is not None and existing.status in ("pending", "running"):
            return existing
        return await self._reports.create_pending(user_id, patient_id, meeting_id)

    async def get(self, user_id: uuid.UUID, meeting_id: uuid.UUID) -> StoredReport | None:
        return await self._reports.get_by_meeting_id(user_id, meeting_id)

    async def list_for_patient(
        self,
        user_id: uuid.UUID,
        patient_id: uuid.UUID,
    ) -> list[StoredReport]:
        return await self._reports.list_for_patient(user_id, patient_id)

    async def latest_ready_summary_excerpt(
        self,
        user_id: uuid.UUID,
        patient_id: uuid.UUID,
        *,
        before_start_at: datetime | None = None,
        max_chars: int = 600,
    ) -> str | None:
        if before_start_at is not None:
            ready = await self._summaries.list_ready_before_meeting(
                user_id,
                patient_id,
                before_start_at=before_start_at,
                limit=1,
            )
        else:
            ready = await self._summaries.list_ready_for_patient(user_id, patient_id, limit=1)
        if not ready:
            return None
        text = ready[0].text.strip()
        if len(text) <= max_chars:
            return text
        return text[: max_chars - 1].rstrip() + "…"

    async def generate(
        self,
        user_id: uuid.UUID,
        patient_id: uuid.UUID,
        meeting_id: uuid.UUID,
    ) -> None:
        meeting = await self.verify_meeting_for_patient(user_id, patient_id, meeting_id)
        ready = await self._summaries.list_ready_before_meeting(
            user_id,
            patient_id,
            before_start_at=meeting.start_at,
            limit=self._summary_limit,
        )
        if not ready:
            await self._reports.mark_failed(user_id, meeting_id, error=NO_READY_SUMMARIES_ERROR)
            return

        chronological = list(reversed(ready))
        await self._reports.mark_running(user_id, meeting_id)

        try:
            generated = await self._synthesizer.synthesize(summaries=chronological)
        except Exception as exc:
            logger.error("next-meeting report generation failed", exc_info=exc)
            await self._reports.mark_failed(user_id, meeting_id, error=str(exc))
            return

        open_topics = list(generated.open_topics)
        if not open_topics:
            open_topics = bullets_under_heading(ready[0].text, FOLLOWUP_HEADING)

        await self._reports.mark_ready(
            user_id,
            meeting_id,
            intro=generated.intro,
            changes=generated.changes,
            open_topics=open_topics,
            source_meeting_ids=[item.meeting_id for item in chronological],
            model=generated.model,
        )
