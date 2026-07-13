import logging
import uuid
from typing import TYPE_CHECKING

from core.config import Settings
from core.database import get_sessionmaker
from reports.models import StoredReport
from reports.parse import FOLLOWUP_HEADING, bullets_under_heading
from reports.repository import NextMeetingReportRepository
from reports.synthesizer import OllamaReportSynthesizer, ReportSynthesizer
from summaries.repository import SummaryRepository

logger = logging.getLogger(__name__)

NO_READY_SUMMARIES_ERROR = "אין סיכומי פגישות מוכנים"


def build_synthesizer(settings: Settings) -> ReportSynthesizer:
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
            report.patient_id,
            error="generation was interrupted by a server restart",
        )
    if stranded:
        logger.warning("failed %d next-meeting reports interrupted by restart", len(stranded))
    return len(stranded)


async def run_report_generation(patient_id: uuid.UUID, settings: Settings) -> None:
    """Background entrypoint — opens its own session (request session is closed)."""
    if not settings.database_url:
        return
    sessionmaker = get_sessionmaker(settings.database_url)
    async with sessionmaker() as session:
        service = NextMeetingReportService(
            reports=NextMeetingReportRepository(session),
            summaries=SummaryRepository(session),
            synthesizer=build_synthesizer(settings),
        )
        await service.generate(patient_id)


class NextMeetingReportService:
    """Builds a cross-meeting prep brief from ready per-meeting summaries."""

    def __init__(
        self,
        *,
        reports: NextMeetingReportRepository,
        summaries: SummaryRepository,
        synthesizer: ReportSynthesizer,
        summary_limit: int = 8,
    ) -> None:
        self._reports = reports
        self._summaries = summaries
        self._synthesizer = synthesizer
        self._summary_limit = summary_limit

    async def create_pending(self, patient_id: uuid.UUID) -> StoredReport:
        existing = await self._reports.get_by_patient_id(patient_id)
        if existing is not None and existing.status in ("pending", "running"):
            return existing
        return await self._reports.create_pending(patient_id)

    async def get(self, patient_id: uuid.UUID) -> StoredReport | None:
        return await self._reports.get_by_patient_id(patient_id)

    async def latest_ready_summary_excerpt(
        self,
        patient_id: uuid.UUID,
        *,
        max_chars: int = 600,
    ) -> str | None:
        ready = await self._summaries.list_ready_for_patient(patient_id, limit=1)
        if not ready:
            return None
        text = ready[0].text.strip()
        if len(text) <= max_chars:
            return text
        return text[: max_chars - 1].rstrip() + "…"

    async def generate(self, patient_id: uuid.UUID) -> None:
        ready = await self._summaries.list_ready_for_patient(
            patient_id,
            limit=self._summary_limit,
        )
        if not ready:
            await self._reports.mark_failed(patient_id, error=NO_READY_SUMMARIES_ERROR)
            return

        # Chronological for the model (oldest → newest); repo returns newest first.
        chronological = list(reversed(ready))
        await self._reports.mark_running(patient_id)

        try:
            generated = await self._synthesizer.synthesize(summaries=chronological)
        except Exception as exc:
            logger.error("next-meeting report generation failed", exc_info=exc)
            await self._reports.mark_failed(patient_id, error=str(exc))
            return

        open_topics = list(generated.open_topics)
        if not open_topics:
            # Newest summary first in `ready`; fall back to its follow-up bullets.
            open_topics = bullets_under_heading(ready[0].text, FOLLOWUP_HEADING)

        await self._reports.mark_ready(
            patient_id,
            intro=generated.intro,
            changes=generated.changes,
            open_topics=open_topics,
            source_meeting_ids=[item.meeting_id for item in chronological],
            model=generated.model,
        )
