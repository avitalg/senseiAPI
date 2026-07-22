import logging
from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any, Literal, Protocol
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


class OpenAIClient(Protocol):
    """Structural type for the OpenAI SDK chat client."""

    @property
    def chat(self) -> Any: ...


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


def format_meeting_context_for_prompt(meeting: DailyMeetingContext) -> str:
    """Format one clinical context without exposing identity or other meetings."""
    details: list[str] = []
    if meeting.intro and meeting.intro.strip():
        details.append(f"סקירה: {meeting.intro.strip()}")
    if meeting.changes:
        details.append(f"{CHANGES_HEADING.removeprefix('## ')}: " + "; ".join(meeting.changes))
    if meeting.open_topics:
        details.append(f"{OPEN_HEADING.removeprefix('## ')}: " + "; ".join(meeting.open_topics))
    return "\n".join(details) or "אין פרטים נוספים בדוח ההכנה."


def _with_terminal_punctuation(text: str) -> str:
    stripped = text.strip()
    if stripped.endswith((".", "!", "?")):
        return stripped
    return f"{stripped}."


def _meeting_prefix(
    meeting: DailyMeetingContext,
    *,
    time_zone: ZoneInfo,
    is_first: bool,
) -> str:
    start = _in_time_zone(meeting.start_at, time_zone).strftime("%H:%M")
    transition = "" if is_first else "לאחר מכן, "
    return f"{transition}בשעה {start} תתקיים הפגישה שלך עם {meeting.patient_name}."


class _BaseDailyReportSynthesizer(DailyReportSynthesizer):
    """Assemble one daily brief while keeping each patient's LLM context isolated."""

    def __init__(self, *, model: str) -> None:
        self._model = model

    @abstractmethod
    async def _generate_fragment(self, user_text: str) -> str: ...

    async def synthesize(
        self,
        *,
        meetings: Sequence[DailyMeetingContext],
        time_zone: ZoneInfo,
    ) -> GeneratedDailyReport:
        if not meetings:
            raise DailyReportFailedError("cannot synthesize a daily report without meetings")

        count = len(meetings)
        day_intro = (
            "היום ביומן שלך מתוכננת פגישה אחת."
            if count == 1
            else f"היום ביומן שלך מתוכננות {count} פגישות."
        )
        parts = [day_intro]
        raw_outputs: list[str] = []

        for index, meeting in enumerate(meetings):
            parts.append(_meeting_prefix(meeting, time_zone=time_zone, is_first=index == 0))
            if not meeting.context_available:
                parts.append("אין דוח הכנה זמין לפגישה זו.")
                continue

            user_text = format_meeting_context_for_prompt(meeting)
            raw = await self._generate_fragment(user_text)
            raw_outputs.append(raw)
            parts.append(_with_terminal_punctuation(parse_daily_report_output(raw)))

        return GeneratedDailyReport(
            text=" ".join(parts),
            model=self._model,
            raw_text="\n".join(raw_outputs),
        )


class OllamaDailyReportSynthesizer(_BaseDailyReportSynthesizer):
    def __init__(self, *, client: OllamaClient, model: str, num_ctx: int) -> None:
        super().__init__(model=model)
        self._client = client
        self._num_ctx = num_ctx

    async def _generate_fragment(self, user_text: str) -> str:
        try:
            response = await self._client.chat(
                model=self._model,
                messages=[
                    {"role": "system", "content": DAILY_REPORT_SYSTEM_PROMPT},
                    {"role": "user", "content": user_text},
                ],
                options={"num_ctx": self._num_ctx, "temperature": 0},
                format="json",
            )
        except Exception as exc:
            logger.error("ollama daily report synthesis failed", exc_info=exc)
            raise DailyReportFailedError(f"daily report generation failed: {exc}") from exc

        content = response.message.content
        if content is None or not content.strip():
            raise DailyReportFailedError("the model returned an empty daily report")
        return content.strip()


class OpenAIDailyReportSynthesizer(_BaseDailyReportSynthesizer):
    """Daily-report synthesis through hosted OpenAI Chat Completions.

    Meeting-report text leaves the host; use only when SUMMARY_BACKEND=openai is intentional.
    """

    def __init__(self, *, client: OpenAIClient, model: str) -> None:
        super().__init__(model=model)
        self._client = client

    async def _generate_fragment(self, user_text: str) -> str:
        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": DAILY_REPORT_SYSTEM_PROMPT},
                    {"role": "user", "content": user_text},
                ],
                temperature=0,
            )
        except Exception as exc:
            logger.error("openai daily report synthesis failed", exc_info=exc)
            raise DailyReportFailedError(f"daily report generation failed: {exc}") from exc

        try:
            raw = (response.choices[0].message.content or "").strip()
        except (AttributeError, IndexError, TypeError) as exc:
            raise DailyReportFailedError("the model returned an empty daily report") from exc
        if not raw:
            raise DailyReportFailedError("the model returned an empty daily report")
        return raw
