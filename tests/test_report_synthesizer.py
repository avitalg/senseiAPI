import uuid
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import MagicMock

import pytest

from core.config import Settings
from reports.models import ReportFailedError
from reports.service import build_synthesizer
from reports.synthesizer import (
    OllamaReportSynthesizer,
    OpenAIReportSynthesizer,
    format_summaries_for_prompt,
)
from summaries.models import ReadyMeetingSummary

MEETING_ID = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
NOW = datetime(2026, 7, 17, 10, 0, tzinfo=UTC)

SAMPLE_JSON = """\
{
  "intro": "סקירה קצרה",
  "changes": ["שינוי א"],
  "open_topics": ["נושא א"]
}
"""


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def _summary(*, text: str = "סיכום פגישה") -> ReadyMeetingSummary:
    return ReadyMeetingSummary(
        meeting_id=MEETING_ID,
        start_at=NOW - timedelta(days=7),
        text=text,
    )


class _FakeOllamaClient:
    def __init__(self, content: str = SAMPLE_JSON, error: Exception | None = None) -> None:
        self._content = content
        self._error = error
        self.calls: list[dict[str, Any]] = []

    async def chat(
        self,
        model: str,
        messages: Sequence[Mapping[str, str]],
        *,
        options: Mapping[str, int],
    ) -> dict[str, Any]:
        self.calls.append({"model": model, "messages": messages, "options": options})
        if self._error is not None:
            raise self._error
        return {"message": {"content": self._content}}


class _FakeOpenAIClient:
    def __init__(self, content: str = SAMPLE_JSON, error: Exception | None = None) -> None:
        self._content = content
        self._error = error
        self.calls: list[dict[str, Any]] = []
        self.chat = MagicMock()
        self.chat.completions = MagicMock()
        self.chat.completions.create = self._create

    async def _create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        if self._error is not None:
            raise self._error
        msg = MagicMock()
        msg.content = self._content
        choice = MagicMock()
        choice.message = msg
        response = MagicMock()
        response.choices = [choice]
        return response


@pytest.mark.anyio
async def test_ollama_synthesize_returns_parsed_report() -> None:
    client = _FakeOllamaClient()
    synth = OllamaReportSynthesizer(client=client, model="llama3.1:latest", num_ctx=32768)

    report = await synth.synthesize(summaries=[_summary()])

    assert report.intro == "סקירה קצרה"
    assert report.changes == ["שינוי א"]
    assert report.open_topics == ["נושא א"]
    assert report.model == "llama3.1:latest"
    assert client.calls[0]["options"]["num_ctx"] == 32768


@pytest.mark.anyio
async def test_openai_synthesize_returns_parsed_report_with_model() -> None:
    client = _FakeOpenAIClient()
    synth = OpenAIReportSynthesizer(client=client, model="gpt-4o")

    report = await synth.synthesize(summaries=[_summary()])

    assert report.intro == "סקירה קצרה"
    assert report.model == "gpt-4o"
    assert client.calls[0]["model"] == "gpt-4o"
    assert client.calls[0]["temperature"] == 0
    assert "סיכום פגישה" in client.calls[0]["messages"][1]["content"]


@pytest.mark.anyio
async def test_openai_synthesize_wraps_api_errors() -> None:
    client = _FakeOpenAIClient(error=RuntimeError("rate limited"))
    synth = OpenAIReportSynthesizer(client=client, model="gpt-4o")

    with pytest.raises(ReportFailedError):
        await synth.synthesize(summaries=[_summary()])


@pytest.mark.anyio
async def test_openai_synthesize_rejects_empty_content() -> None:
    client = _FakeOpenAIClient(content="   ")
    synth = OpenAIReportSynthesizer(client=client, model="gpt-4o")

    with pytest.raises(ReportFailedError):
        await synth.synthesize(summaries=[_summary()])


def test_format_summaries_includes_meeting_text() -> None:
    text = format_summaries_for_prompt([_summary(text="תוכן מיוחד")])
    assert "תוכן מיוחד" in text
    assert str(MEETING_ID) in text


def test_build_synthesizer_openai_requires_api_key() -> None:
    settings = Settings(
        summary_backend="openai",
        openai_api_key=None,
        enable_security=False,
        auth_token_secret_key=None,
        database_url=None,
    )
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        build_synthesizer(settings)


def test_build_synthesizer_selects_openai(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_cls = MagicMock(return_value=MagicMock())
    monkeypatch.setattr("openai.AsyncOpenAI", fake_cls)
    settings = Settings(
        summary_backend="openai",
        openai_api_key="sk-test",
        openai_model="gpt-4o",
        enable_security=False,
        auth_token_secret_key=None,
        database_url=None,
    )
    synth = build_synthesizer(settings)
    assert isinstance(synth, OpenAIReportSynthesizer)
    fake_cls.assert_called_once_with(api_key="sk-test")


def test_build_synthesizer_selects_ollama(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_cls = MagicMock(return_value=MagicMock())
    monkeypatch.setattr("ollama.AsyncClient", fake_cls)
    settings = Settings(
        summary_backend="ollama",
        ollama_host="http://localhost:11434",
        ollama_model="llama3.1:latest",
        enable_security=False,
        auth_token_secret_key=None,
        database_url=None,
    )
    synth = build_synthesizer(settings)
    assert isinstance(synth, OllamaReportSynthesizer)
    fake_cls.assert_called_once()
