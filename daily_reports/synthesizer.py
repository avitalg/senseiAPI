import logging
from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Literal, Protocol
from zoneinfo import ZoneInfo

from ollama import ChatResponse

from daily_reports.models import DailyMeetingContext, DailyReportFailedError, GeneratedDailyReport
from daily_reports.parse import parse_daily_report_output
from daily_reports.prompt import DAILY_REPORT_SYSTEM_PROMPT
from reports.parse import CHANGES_HEADING, OPEN_HEADING

logger = logging.getLogger(__name__)


class OllamaClient(Protocol):
    async def chat(
        self,
        model: str,
        messages: Sequence[Mapping[str, str]],
        *,
        options: Mapping[str, int],
        format: Literal["json"],
    ) -> ChatResponse: ...


class DailyReportSynthesizer(ABC):
    """Turns ordered meeting prep reports into one speech-friendly daily brief."""

    @abstractmethod
    async def synthesize(
        self,
        *,
        meetings: Sequence[DailyMeetingContext],
        time_zone: ZoneInfo,
    ) -> GeneratedDailyReport: ...


def _in_time_zone(value: datetime, time_zone: ZoneInfo) -> datetime:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(time_zone)


def format_meetings_for_prompt(
    meetings: Sequence[DailyMeetingContext],
    *,
    time_zone: ZoneInfo,
) -> str:
    blocks: list[str] = []
    for index, meeting in enumerate(meetings, start=1):
        start = _in_time_zone(meeting.start_at, time_zone).strftime("%H:%M")
        if meeting.context_available:
            details: list[str] = []
            if meeting.intro and meeting.intro.strip():
                details.append(f"סקירה: {meeting.intro.strip()}")
            if meeting.changes:
                details.append(
                    f"{CHANGES_HEADING.removeprefix('## ')}: " + "; ".join(meeting.changes)
                )
            if meeting.open_topics:
                details.append(
                    f"{OPEN_HEADING.removeprefix('## ')}: " + "; ".join(meeting.open_topics)
                )
            context = "\n".join(details) or "אין פרטים נוספים בדוח ההכנה."
        else:
            context = "אין דוח הכנה זמין לפגישה זו."
        blocks.append(
            f"פגישה {index}\n"
            f"שעה: {start}\n"
            f"שם המטופל/ת: {meeting.patient_name}\n"
            f"דוח הכנה:\n{context}"
        )
    return "\n\n---\n\n".join(blocks)


class OllamaDailyReportSynthesizer(DailyReportSynthesizer):
    def __init__(self, *, client: OllamaClient, model: str, num_ctx: int) -> None:
        self._client = client
        self._model = model
        self._num_ctx = num_ctx

    async def synthesize(
        self,
        *,
        meetings: Sequence[DailyMeetingContext],
        time_zone: ZoneInfo,
    ) -> GeneratedDailyReport:
        user_text = format_meetings_for_prompt(meetings, time_zone=time_zone)
        try:
            response = await self._client.chat(
                model=self._model,
                messages=[
                    {"role": "system", "content": DAILY_REPORT_SYSTEM_PROMPT},
                    {"role": "user", "content": user_text},
                ],
                options={"num_ctx": self._num_ctx},
                format="json",
            )
        except Exception as exc:
            logger.error("ollama daily report synthesis failed", exc_info=exc)
            raise DailyReportFailedError(f"daily report generation failed: {exc}") from exc

        content = response.message.content
        if content is None or not content.strip():
            raise DailyReportFailedError("the model returned an empty daily report")
        raw = content.strip()
        text = parse_daily_report_output(raw)
        return GeneratedDailyReport(text=text, model=self._model, raw_text=raw)
