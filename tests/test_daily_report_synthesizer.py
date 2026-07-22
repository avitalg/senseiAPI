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
    format_meeting_context_for_prompt,
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


def test_format_meeting_context_excludes_identity_schedule_and_ids() -> None:
    formatted = format_meeting_context_for_prompt(_context())

    assert "מצב יציב" in formatted
    assert "09:30" not in formatted
    assert "דנה" not in formatted
    assert "aaaaaaaa-aaaa" not in formatted
    assert "bbbbbbbb-bbbb" not in formatted


def test_format_meeting_context_marks_empty_ready_report() -> None:
    formatted = format_meeting_context_for_prompt(_context(available=False))

    assert formatted == "אין פרטים נוספים בדוח ההכנה."
    assert "שיפור בוויסות" not in formatted


class _FakeOllamaClient:
    def __init__(
        self,
        *,
        contents: Sequence[str | None] = ('{"text": "כדאי לזכור את השיפור בוויסות"}',),
    ) -> None:
        self.calls: list[Sequence[Mapping[str, str]]] = []
        self.contents = list(contents)
        self.format: Literal["json"] | None = None
        self.options: Mapping[str, int] = {}

    async def chat(
        self,
        model: str,
        messages: Sequence[Mapping[str, str]],
        *,
        options: Mapping[str, int],
        format: Literal["json"],
    ) -> ChatResponse:
        self.calls.append(messages)
        self.format = format
        self.options = options
        return ChatResponse(message=Message(role="assistant", content=self.contents.pop(0)))


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

    assert generated.text == (
        "היום ביומן שלך מתוכננת פגישה אחת. "
        "בשעה 09:30 תתקיים הפגישה שלך עם דנה. כדאי לזכור את השיפור בוויסות."
    )
    assert generated.model == "test-model"
    assert client.calls[0][0]["role"] == "system"
    assert "להקראה בקול" in client.calls[0][0]["content"]
    assert "יום העבודה של המטפל/ת" in client.calls[0][0]["content"]
    assert "מטופל/ת אחד/ת בלבד" in client.calls[0][0]["content"]
    assert "אל תעביר מידע בין מטופלים" in client.calls[0][0]["content"]
    assert "שני משפטים לכל היותר" in client.calls[0][0]["content"]
    assert "שפת הפלט היא עברית בלבד" in client.calls[0][0]["content"]
    assert "אסור לכתוב באנגלית" in client.calls[0][0]["content"]
    assert "כתוב עכשיו את התזכורת לפגישה היחידה" in client.calls[0][0]["content"]
    assert client.options["temperature"] == 0
    assert client.format == "json"


@pytest.mark.anyio
async def test_synthesizer_isolates_each_patient_in_a_separate_model_call() -> None:
    first = _context()
    second = DailyMeetingContext(
        meeting_id=uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc"),
        patient_id=uuid.UUID("dddddddd-dddd-dddd-dddd-dddddddddddd"),
        patient_name="יואב",
        start_at=datetime(2026, 7, 21, 8, 0, tzinfo=UTC),
        intro="מתח בעבודה",
        changes=["שינה פחות טובה"],
        open_topics=["גבולות בעבודה"],
        context_available=True,
    )
    client = _FakeOllamaClient(
        contents=(
            '{"text": "לזכור את השיפור בוויסות"}',
            '{"text": "לחזור למתח ולגבולות בעבודה"}',
        )
    )
    synthesizer = OllamaDailyReportSynthesizer(
        client=client,
        model="test-model",
        num_ctx=4096,
    )

    generated = await synthesizer.synthesize(
        meetings=[first, second],
        time_zone=ZoneInfo("Asia/Jerusalem"),
    )

    assert len(client.calls) == 2
    first_input = client.calls[0][1]["content"]
    second_input = client.calls[1][1]["content"]
    assert "שיפור בוויסות" in first_input
    assert "מתח בעבודה" not in first_input
    assert "דנה" not in first_input
    assert "מתח בעבודה" in second_input
    assert "שיפור בוויסות" not in second_input
    assert "יואב" not in second_input
    assert generated.text == (
        "היום ביומן שלך מתוכננות 2 פגישות. "
        "בשעה 09:30 תתקיים הפגישה שלך עם דנה. לזכור את השיפור בוויסות. "
        "לאחר מכן, בשעה 11:00 תתקיים הפגישה שלך עם יואב. "
        "לחזור למתח ולגבולות בעבודה."
    )


@pytest.mark.anyio
async def test_synthesizer_skips_model_for_meeting_without_context() -> None:
    client = _FakeOllamaClient(contents=())
    synthesizer = OllamaDailyReportSynthesizer(
        client=client,
        model="test-model",
        num_ctx=4096,
    )

    generated = await synthesizer.synthesize(
        meetings=[_context(available=False)],
        time_zone=ZoneInfo("Asia/Jerusalem"),
    )

    assert client.calls == []
    assert generated.text.endswith("אין דוח הכנה זמין לפגישה זו.")


@pytest.mark.anyio
@pytest.mark.parametrize("content", [None, "", "   "])
async def test_synthesizer_rejects_missing_or_empty_content(content: str | None) -> None:
    synthesizer = OllamaDailyReportSynthesizer(
        client=_FakeOllamaClient(contents=(content,)),
        model="test-model",
        num_ctx=4096,
    )

    with pytest.raises(DailyReportFailedError, match="empty daily report"):
        await synthesizer.synthesize(
            meetings=[_context()],
            time_zone=ZoneInfo("Asia/Jerusalem"),
        )
