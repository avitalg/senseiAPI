import uuid
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Literal
from zoneinfo import ZoneInfo

import pytest
from ollama import ChatResponse, Message

from daily_reports.models import DailyMeetingContext, DailyReportFailedError
from daily_reports.synthesizer import (
    OllamaDailyReportSynthesizer,
    format_meetings_for_prompt,
)


def _context(*, available: bool = True) -> DailyMeetingContext:
    return DailyMeetingContext(
        meeting_id=uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
        patient_id=uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"),
        patient_name="דנה",
        start_at=datetime(2026, 7, 21, 6, 30, tzinfo=UTC),
        intro="מצב יציב" if available else None,
        changes=["שיפור בוויסות"] if available else [],
        open_topics=["לחזור לשינה"] if available else [],
        context_available=available,
    )


def test_format_meetings_is_chronological_tts_context_without_ids() -> None:
    formatted = format_meetings_for_prompt(
        [_context()],
        time_zone=ZoneInfo("Asia/Jerusalem"),
    )

    assert "שעה: 09:30" in formatted
    assert "שם המטופל/ת: דנה" in formatted
    assert "מצב יציב" in formatted
    assert "aaaaaaaa-aaaa" not in formatted
    assert "bbbbbbbb-bbbb" not in formatted


def test_format_meetings_marks_missing_context() -> None:
    formatted = format_meetings_for_prompt(
        [_context(available=False)],
        time_zone=ZoneInfo("Asia/Jerusalem"),
    )

    assert "אין דוח הכנה זמין לפגישה זו" in formatted
    assert "שיפור בוויסות" not in formatted


class _FakeOllamaClient:
    def __init__(self, *, content: str | None = '{"text": "היום צפויה פגישה עם דנה."}') -> None:
        self.messages: Sequence[Mapping[str, str]] = []
        self.content = content
        self.format: Literal["json"] | None = None

    async def chat(
        self,
        model: str,
        messages: Sequence[Mapping[str, str]],
        *,
        options: Mapping[str, int],
        format: Literal["json"],
    ) -> ChatResponse:
        self.messages = messages
        self.format = format
        return ChatResponse(message=Message(role="assistant", content=self.content))


@pytest.mark.anyio
async def test_synthesizer_returns_validated_hebrew_text() -> None:
    client = _FakeOllamaClient()
    synthesizer = OllamaDailyReportSynthesizer(
        client=client,
        model="test-model",
        num_ctx=4096,
    )

    generated = await synthesizer.synthesize(
        meetings=[_context()],
        time_zone=ZoneInfo("Asia/Jerusalem"),
    )

    assert generated.text == "היום צפויה פגישה עם דנה."
    assert generated.model == "test-model"
    assert client.messages[0]["role"] == "system"
    assert "להקראה בקול" in client.messages[0]["content"]
    assert client.format == "json"


@pytest.mark.anyio
@pytest.mark.parametrize("content", [None, "", "   "])
async def test_synthesizer_rejects_missing_or_empty_content(content: str | None) -> None:
    synthesizer = OllamaDailyReportSynthesizer(
        client=_FakeOllamaClient(content=content),
        model="test-model",
        num_ctx=4096,
    )

    with pytest.raises(DailyReportFailedError, match="empty daily report"):
        await synthesizer.synthesize(
            meetings=[_context()],
            time_zone=ZoneInfo("Asia/Jerusalem"),
        )
