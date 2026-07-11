import json
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from google import genai

from summaries.models import Summary, SummaryFailedError
from summaries.prompt import SummarySchema
from summaries.summarizer import GeminiSummarizer, MockSummarizer, OllamaSummarizer

HEBREW_TRANSCRIPT = "מטפל: איך עבר עליך השבוע? מטופל: היה קשה, הרבה חרדה."

MODEL_JSON = {
    "summary": "המטופל תיאר שבוע קשה עם חרדה מוגברת.",
    "insights": ["המטופל מדווח על חרדה נמשכת.", "ניכרת נכונות לשתף."],
    "risk_flags": ["המטופל דיווח על שינה מופרעת."],
}


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class _FakeOllamaClient:
    """Stands in for ``ollama.AsyncClient``."""

    def __init__(self, content: str | None = None, error: Exception | None = None) -> None:
        self._content = json.dumps(MODEL_JSON, ensure_ascii=False) if content is None else content
        self._error = error
        self.calls: list[dict[str, Any]] = []

    async def chat(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(kwargs)
        if self._error is not None:
            raise self._error
        return {"message": {"content": self._content}}


def _summarizer(client: _FakeOllamaClient) -> OllamaSummarizer:
    return OllamaSummarizer(client=client, model="qwen2.5:7b-instruct", num_ctx=32768)


@pytest.mark.anyio
async def test_summarize_returns_structured_summary_insights_and_risk_flags() -> None:
    client = _FakeOllamaClient()

    summary = await _summarizer(client).summarize(text=HEBREW_TRANSCRIPT, language="he")

    assert summary == Summary(
        text=MODEL_JSON["summary"],
        insights=tuple(MODEL_JSON["insights"]),
        risk_flags=tuple(MODEL_JSON["risk_flags"]),
        model="qwen2.5:7b-instruct",
    )


@pytest.mark.anyio
async def test_summarize_constrains_the_model_to_a_json_schema() -> None:
    """Ollama's `format` is the equivalent of Gemini's response_schema: without it a 7B
    model will happily answer in prose and the parse blows up."""
    client = _FakeOllamaClient()

    await _summarizer(client).summarize(text=HEBREW_TRANSCRIPT, language="he")

    schema = client.calls[0]["format"]
    assert schema["type"] == "object"
    assert set(schema["properties"]) == {"summary", "insights", "risk_flags"}


@pytest.mark.anyio
async def test_summarize_passes_num_ctx_to_ollama() -> None:
    """Ollama defaults num_ctx to 2048 and silently truncates past it, which would
    summarise the first few minutes of a session and never say so."""
    client = _FakeOllamaClient()

    await _summarizer(client).summarize(text=HEBREW_TRANSCRIPT, language="he")

    assert client.calls[0]["options"]["num_ctx"] == 32768


@pytest.mark.anyio
async def test_summarize_sends_the_transcript_and_system_prompt() -> None:
    client = _FakeOllamaClient()

    await _summarizer(client).summarize(text=HEBREW_TRANSCRIPT, language="he")

    messages = client.calls[0]["messages"]
    assert messages[0]["role"] == "system"
    assert "אבחנה" in messages[0]["content"]
    assert messages[1] == {"role": "user", "content": HEBREW_TRANSCRIPT}


@pytest.mark.anyio
async def test_summarize_accepts_an_empty_risk_flag_list() -> None:
    """A session with nothing concerning is the common case, not a failure."""
    client = _FakeOllamaClient(
        content=json.dumps({"summary": "שיחה שגרתית.", "insights": [], "risk_flags": []})
    )

    summary = await _summarizer(client).summarize(text=HEBREW_TRANSCRIPT, language="he")

    assert summary.risk_flags == ()
    assert summary.text == "שיחה שגרתית."


@pytest.mark.anyio
async def test_summarize_wraps_ollama_errors() -> None:
    client = _FakeOllamaClient(error=ConnectionError("connection refused"))

    with pytest.raises(SummaryFailedError):
        await _summarizer(client).summarize(text=HEBREW_TRANSCRIPT, language="he")


@pytest.mark.anyio
async def test_summarize_rejects_an_unparseable_response() -> None:
    """A small local model can ignore the schema; a broken parse must fail loudly rather
    than persist an empty summary that looks like a real one."""
    client = _FakeOllamaClient(content="I am a helpful assistant! Here is your summary:")

    with pytest.raises(SummaryFailedError):
        await _summarizer(client).summarize(text=HEBREW_TRANSCRIPT, language="he")


@pytest.mark.anyio
async def test_summarize_rejects_an_empty_summary() -> None:
    client = _FakeOllamaClient(
        content=json.dumps({"summary": "  ", "insights": [], "risk_flags": []})
    )

    with pytest.raises(SummaryFailedError):
        await _summarizer(client).summarize(text=HEBREW_TRANSCRIPT, language="he")


@pytest.mark.anyio
async def test_mock_summarizer_returns_canned_data_without_a_model() -> None:
    """Lets the calendar frontend and CI run with no Ollama and no model pulled."""
    summary = await MockSummarizer().summarize(text=HEBREW_TRANSCRIPT, language="he")

    assert summary.text
    assert summary.insights
    assert summary.model == "mock"


class _FakeGeminiModels:
    def __init__(self, parsed: object = None, error: Exception | None = None) -> None:
        self._parsed = parsed
        self._error = error
        self.calls: list[dict[str, Any]] = []

    async def generate_content(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        if self._error is not None:
            raise self._error
        return SimpleNamespace(parsed=self._parsed, text="raw text")


class _FakeGeminiClient:
    """Stands in for ``google.genai.Client``; ``.aio.models`` is the async surface."""

    def __init__(self, parsed: object = None, error: Exception | None = None) -> None:
        self.models = _FakeGeminiModels(parsed=parsed, error=error)
        self.aio = SimpleNamespace(models=self.models)


def _gemini(
    monkeypatch: pytest.MonkeyPatch,
    *,
    parsed: object = None,
    error: Exception | None = None,
) -> tuple[GeminiSummarizer, _FakeGeminiClient]:
    """GeminiSummarizer builds its own client from an api_key (as PR #5 wrote it), so the
    SDK constructor is patched here. No test ever reaches the network."""
    fake = _FakeGeminiClient(parsed=parsed, error=error)
    monkeypatch.setattr(genai, "Client", lambda **_: fake)
    return GeminiSummarizer("fake-api-key", "gemini-2.5-flash"), fake


@pytest.mark.anyio
async def test_gemini_returns_structured_summary_insights_and_risk_flags(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    summarizer, _ = _gemini(
        monkeypatch,
        parsed=SummarySchema(
            summary=MODEL_JSON["summary"],
            insights=MODEL_JSON["insights"],
            risk_flags=MODEL_JSON["risk_flags"],
        ),
    )

    summary = await summarizer.summarize(text=HEBREW_TRANSCRIPT, language="he")

    assert summary == Summary(
        text=MODEL_JSON["summary"],
        insights=tuple(MODEL_JSON["insights"]),
        risk_flags=tuple(MODEL_JSON["risk_flags"]),
        model="gemini-2.5-flash",
    )


@pytest.mark.anyio
async def test_gemini_constrains_the_response_to_a_schema(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Gemini's response_schema is the counterpart of Ollama's `format`."""
    summarizer, fake = _gemini(
        monkeypatch,
        parsed=SummarySchema(summary="סיכום.", insights=[], risk_flags=[]),
    )

    await summarizer.summarize(text=HEBREW_TRANSCRIPT, language="he")

    config = fake.models.calls[0]["config"]
    assert config.response_mime_type == "application/json"
    assert config.response_schema is SummarySchema
    assert HEBREW_TRANSCRIPT in fake.models.calls[0]["contents"]


@pytest.mark.anyio
async def test_gemini_rejects_an_unparseable_response(monkeypatch: pytest.MonkeyPatch) -> None:
    summarizer, _ = _gemini(monkeypatch, parsed=None)

    with pytest.raises(SummaryFailedError):
        await summarizer.summarize(text=HEBREW_TRANSCRIPT, language="he")


@pytest.mark.anyio
async def test_gemini_wraps_api_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    summarizer, _ = _gemini(monkeypatch, error=httpx.ConnectError("connection refused"))

    with pytest.raises(SummaryFailedError):
        await summarizer.summarize(text=HEBREW_TRANSCRIPT, language="he")
