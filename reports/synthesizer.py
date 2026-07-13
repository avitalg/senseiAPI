import logging
from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from typing import Any, Protocol

from reports.models import GeneratedReport, ReportFailedError
from reports.parse import parse_report_output
from reports.prompt import NEXT_MEETING_REPORT_SYSTEM_PROMPT
from summaries.models import ReadyMeetingSummary

logger = logging.getLogger(__name__)


class OllamaClient(Protocol):
    async def chat(
        self,
        model: str,
        messages: Sequence[Mapping[str, str]],
        *,
        options: Mapping[str, int],
    ) -> Any: ...


class ReportSynthesizer(ABC):
    """Turns past meeting summaries into a cross-meeting prep brief."""

    @abstractmethod
    async def synthesize(self, *, summaries: Sequence[ReadyMeetingSummary]) -> GeneratedReport:
        ...


def format_summaries_for_prompt(summaries: Sequence[ReadyMeetingSummary]) -> str:
    blocks: list[str] = []
    for index, item in enumerate(summaries, start=1):
        when = item.start_at.isoformat()
        blocks.append(
            f"### פגישה {index}\n"
            f"מזהה פגישה: {item.meeting_id}\n"
            f"תאריך: {when}\n\n"
            f"{item.text.strip()}"
        )
    return "\n\n---\n\n".join(blocks)


class OllamaReportSynthesizer(ReportSynthesizer):
    def __init__(self, *, client: OllamaClient, model: str, num_ctx: int) -> None:
        self._client = client
        self._model = model
        self._num_ctx = num_ctx

    async def synthesize(self, *, summaries: Sequence[ReadyMeetingSummary]) -> GeneratedReport:
        user_text = format_summaries_for_prompt(summaries)
        try:
            response = await self._client.chat(
                model=self._model,
                messages=[
                    {"role": "system", "content": NEXT_MEETING_REPORT_SYSTEM_PROMPT},
                    {"role": "user", "content": user_text},
                ],
                options={"num_ctx": self._num_ctx},
            )
        except Exception as exc:
            logger.error("ollama report synthesis failed", exc_info=exc)
            raise ReportFailedError(f"report generation failed: {exc}") from exc

        raw = response["message"]["content"].strip()
        if not raw:
            raise ReportFailedError("the model returned an empty report")

        intro, changes, open_topics = parse_report_output(raw)
        return GeneratedReport(
            intro=intro,
            changes=changes,
            open_topics=open_topics,
            model=self._model,
            raw_text=raw,
        )
