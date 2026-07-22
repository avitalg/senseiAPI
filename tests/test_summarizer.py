from collections.abc import Mapping, Sequence
from typing import Any
from unittest.mock import MagicMock

import pytest

from core.config import Settings
from summaries.dependencies import get_summarizer
from summaries.models import Summary, SummaryFailedError
from summaries.summarizer import OllamaSummarizer, OpenAISummarizer

HEBREW_TRANSCRIPT = "מטפל: איך עבר עליך השבוע? מטופל: היה קשה, הרבה חרדה."
HEBREW_SUMMARY = "## נושאים מרכזיים\nחרדה במהלך השבוע."


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class _FakeOllamaClient:
    """Stands in for ``ollama.AsyncClient``."""

    def __init__(self, content: str = HEBREW_SUMMARY, error: Exception | None = None) -> None:
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
    """Minimal stand-in for ``openai.AsyncOpenAI`` chat.completions."""

    def __init__(self, content: str = HEBREW_SUMMARY, error: Exception | None = None) -> None:
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
async def test_summarize_returns_the_models_summary() -> None:
    client = _FakeOllamaClient()
    summarizer = OllamaSummarizer(client=client, model="qwen2.5:7b-instruct", num_ctx=32768)

    summary = await summarizer.summarize(text=HEBREW_TRANSCRIPT, language="he")

    assert summary == Summary(text=HEBREW_SUMMARY, model="qwen2.5:7b-instruct")


@pytest.mark.anyio
async def test_summarize_passes_num_ctx_to_ollama() -> None:
    """Ollama defaults num_ctx to 2048 and silently truncates past it, which would
    summarise the first few minutes of a session and never say so."""
    client = _FakeOllamaClient()
    summarizer = OllamaSummarizer(client=client, model="qwen2.5:7b-instruct", num_ctx=32768)

    await summarizer.summarize(text=HEBREW_TRANSCRIPT, language="he")

    assert client.calls[0]["options"]["num_ctx"] == 32768


@pytest.mark.anyio
async def test_summarize_sends_the_transcript_and_system_prompt() -> None:
    client = _FakeOllamaClient()
    summarizer = OllamaSummarizer(client=client, model="qwen2.5:7b-instruct", num_ctx=32768)

    await summarizer.summarize(text=HEBREW_TRANSCRIPT, language="he")

    messages = client.calls[0]["messages"]
    assert messages[0]["role"] == "system"
    assert "לא נאמרו אמירות מפורשות של סיכון" in messages[0]["content"]
    assert messages[1] == {"role": "user", "content": HEBREW_TRANSCRIPT}


@pytest.mark.anyio
async def test_summarize_wraps_ollama_errors() -> None:
    client = _FakeOllamaClient(error=ConnectionError("connection refused"))
    summarizer = OllamaSummarizer(client=client, model="qwen2.5:7b-instruct", num_ctx=32768)

    with pytest.raises(SummaryFailedError):
        await summarizer.summarize(text=HEBREW_TRANSCRIPT, language="he")


@pytest.mark.anyio
async def test_summarize_normalizes_json_to_markdown() -> None:
    payload = """\
{
  "main_topics": "חרדה",
  "therapist_interventions": "שיקוף",
  "risk_signs": "לא נאמרו אמירות מפורשות של סיכון",
  "follow_up": ["שינה"]
}
"""
    client = _FakeOllamaClient(content=payload)
    summarizer = OllamaSummarizer(client=client, model="qwen2.5:7b-instruct", num_ctx=32768)

    summary = await summarizer.summarize(text=HEBREW_TRANSCRIPT, language="he")

    assert "## נושאים מרכזיים" in summary.text
    assert "## המשך ומעקב" in summary.text
    assert "- שינה" in summary.text


@pytest.mark.anyio
async def test_summarize_rejects_an_empty_response() -> None:
    """An empty summary is a failure, not a session with nothing in it."""
    client = _FakeOllamaClient(content="   ")
    summarizer = OllamaSummarizer(client=client, model="qwen2.5:7b-instruct", num_ctx=32768)

    with pytest.raises(SummaryFailedError):
        await summarizer.summarize(text=HEBREW_TRANSCRIPT, language="he")


@pytest.mark.anyio
async def test_openai_summarize_returns_the_models_summary() -> None:
    client = _FakeOpenAIClient()
    summarizer = OpenAISummarizer(client=client, model="gpt-4o")

    summary = await summarizer.summarize(text=HEBREW_TRANSCRIPT, language="he")

    assert summary == Summary(text=HEBREW_SUMMARY, model="gpt-4o")
    assert client.calls[0]["model"] == "gpt-4o"
    assert client.calls[0]["temperature"] == 0
    assert client.calls[0]["messages"][1]["content"] == HEBREW_TRANSCRIPT


@pytest.mark.anyio
async def test_openai_summarize_wraps_api_errors() -> None:
    client = _FakeOpenAIClient(error=RuntimeError("rate limited"))
    summarizer = OpenAISummarizer(client=client, model="gpt-4o")

    with pytest.raises(SummaryFailedError):
        await summarizer.summarize(text=HEBREW_TRANSCRIPT, language="he")


@pytest.mark.anyio
async def test_openai_summarize_rejects_empty_content() -> None:
    client = _FakeOpenAIClient(content="   ")
    summarizer = OpenAISummarizer(client=client, model="gpt-4o")

    with pytest.raises(SummaryFailedError):
        await summarizer.summarize(text=HEBREW_TRANSCRIPT, language="he")


def test_get_summarizer_openai_requires_api_key() -> None:
    settings = Settings(
        summary_backend="openai",
        openai_api_key=None,
        enable_security=False,
        auth_token_secret_key=None,
        database_url=None,
    )
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        get_summarizer(settings)


def test_get_summarizer_selects_openai(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_cls = MagicMock(return_value=MagicMock())
    monkeypatch.setattr("openai.AsyncOpenAI", fake_cls)
    settings = Settings(
        summary_backend="openai",
        openai_api_key="sk-test",
        openai_model="gpt-4o-mini",
        enable_security=False,
        auth_token_secret_key=None,
        database_url=None,
    )
    summarizer = get_summarizer(settings)
    assert isinstance(summarizer, OpenAISummarizer)
    fake_cls.assert_called_once_with(api_key="sk-test", base_url=None)


def test_get_summarizer_selects_ollama(monkeypatch: pytest.MonkeyPatch) -> None:
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
    summarizer = get_summarizer(settings)
    assert isinstance(summarizer, OllamaSummarizer)
    fake_cls.assert_called_once()
