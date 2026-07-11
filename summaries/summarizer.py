import json
import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from summaries.models import Summary, SummaryFailedError
from summaries.prompt import SUMMARY_JSON_SCHEMA, THERAPIST_SUMMARY_SYSTEM_PROMPT

if TYPE_CHECKING:
    from ollama import AsyncClient

logger = logging.getLogger(__name__)


class Summarizer(ABC):
    """Turns a transcript into a session summary."""

    @abstractmethod
    async def summarize(self, *, text: str, language: str) -> Summary: ...


class OllamaSummarizer(Summarizer):
    """Summarization by a local model served by Ollama (Qwen by default).

    Local means the transcript never leaves this host, which is the point: therapy
    transcripts are PHI.
    """

    def __init__(self, *, client: "AsyncClient", model: str, num_ctx: int) -> None:
        self._client = client
        self._model = model
        self._num_ctx = num_ctx

    async def summarize(self, *, text: str, language: str) -> Summary:
        try:
            response = await self._client.chat(
                model=self._model,
                messages=[
                    {"role": "system", "content": THERAPIST_SUMMARY_SYSTEM_PROMPT},
                    {"role": "user", "content": text},
                ],
                # Constrains decoding to valid JSON. Without it a 7B model drifts into
                # prose or a preamble and the parse below fails.
                format=SUMMARY_JSON_SCHEMA,
                # Ollama defaults num_ctx to 2048 and silently truncates anything longer,
                # which would summarise the opening minutes of a session and say nothing.
                options={"num_ctx": self._num_ctx},
            )
        except Exception as exc:
            logger.error("ollama summarization failed", exc_info=exc)
            raise SummaryFailedError(f"summarization failed: {exc}") from exc

        return _parse(response["message"]["content"], model=self._model)


def _parse(content: str, *, model: str) -> Summary:
    try:
        payload = json.loads(content)
    except json.JSONDecodeError as exc:
        # Better a visible failure than a row that looks like a real summary but is not.
        raise SummaryFailedError(f"the model did not return valid JSON: {content[:200]!r}") from exc

    summary_text = str(payload.get("summary", "")).strip()
    if not summary_text:
        raise SummaryFailedError("the model returned an empty summary")

    return Summary(
        text=summary_text,
        model=model,
        insights=tuple(payload.get("insights") or ()),
        risk_flags=tuple(payload.get("risk_flags") or ()),
    )


class MockSummarizer(Summarizer):
    """Canned output, so the calendar frontend and CI can run with no model pulled.

    Opt-in only (``SUMMARY_BACKEND=mock``): serving invented clinical content by default
    is not a mistake worth risking in a therapy product.
    """

    async def summarize(self, *, text: str, language: str) -> Summary:
        return Summary(
            text=(
                "המטופל תיאר אירוע מצוקה מהשבוע האחרון ותחושות של דריכות והימנעות. "
                "הפגישה התמקדה בטכניקות הרגעה ובחיזוק תחושת הביטחון."
            ),
            model="mock",
            insights=(
                "המטופל מדווח על דריכות מוגברת ועל הימנעות ממקומות מוכרים.",
                "המטפל/ת הציג/ה טכניקות הרגעה; המטופל שיתף פעולה.",
                "הברית הטיפולית נראית יציבה; המטופל היה פתוח לשיתוף.",
            ),
            risk_flags=(
                "המטופל דיווח על שינה מופרעת וסיוטים חוזרים בשבוע האחרון.",
                "ניכרה מצוקה רגשית מוגברת בעת הדיון באירוע.",
            ),
        )
