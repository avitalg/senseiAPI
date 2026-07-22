from collections.abc import AsyncIterator, Iterator, Sequence
from contextlib import contextmanager
from types import SimpleNamespace
from typing import Any

from fastapi.testclient import TestClient

from assistant.client import (
    AssistantClient,
    AssistantError,
    OpenAIAssistant,
    StreamEvent,
    TextChunk,
)
from assistant.dependencies import get_assistant_service
from assistant.service import AssistantService
from assistant.tools import Tools
from assistant.tracing import ChatTrace, Tracer
from auth.router import TEST_USER
from core.config import Settings, get_settings
from main import app


class _RecordingTrace(ChatTrace):
    def set_output(self, text: str) -> None: ...

    def set_error(self, message: str) -> None: ...


class _RecordingTracer(Tracer):
    def __init__(self) -> None:
        self.calls: list[tuple[str | None, str | None]] = []

    @contextmanager
    def trace_chat(self, *, user_id: str | None, session_id: str | None) -> Iterator[ChatTrace]:
        self.calls.append((user_id, session_id))
        yield _RecordingTrace()


class _FakeAssistant(AssistantClient):
    def __init__(self, deltas: list[str], error: str | None = None) -> None:
        self._deltas = deltas
        self._error = error

    async def stream(self, messages: Sequence[dict[str, Any]]) -> AsyncIterator[StreamEvent]:
        for delta in self._deltas:
            yield TextChunk(delta)
        if self._error is not None:
            raise AssistantError(self._error)


def _client(deltas: list[str], error: str | None = None) -> TestClient:
    service = AssistantService(client=_FakeAssistant(deltas, error))
    app.dependency_overrides[get_assistant_service] = lambda: service
    return TestClient(app)


_BODY = {"messages": [{"role": "user", "parts": [{"type": "text", "text": "שלום"}]}]}


def teardown_function() -> None:
    app.dependency_overrides.clear()


def test_chat_streams_the_ai_sdk_ui_message_protocol() -> None:
    client = _client(["שלום", " עולם"])

    res = client.post("/assistant/chat", json=_BODY)

    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/event-stream")
    assert res.headers["x-vercel-ai-ui-message-stream"] == "v1"
    body = res.text
    assert '"type":"start"' in body
    assert '"delta":"שלום"' in body
    assert '"type":"finish"' in body
    assert body.rstrip().endswith("[DONE]")


def test_chat_reports_a_model_failure_as_an_error_part_not_a_500() -> None:
    client = _client([], error="model overloaded")

    res = client.post("/assistant/chat", json=_BODY)

    assert res.status_code == 200
    assert '"type":"error"' in res.text
    assert "model overloaded" in res.text


def test_chat_rejects_an_overlong_question() -> None:
    """A user question past the char cap is refused with 422 before streaming."""
    client = _client(["ok"])
    body = {"messages": [{"role": "user", "parts": [{"type": "text", "text": "א" * 5000}]}]}

    res = client.post("/assistant/chat", json=body)

    assert res.status_code == 422


def test_chat_rejects_a_request_with_no_user_question() -> None:
    """Degenerate bodies (no messages / empty / no text parts) must not invoke the
    paid model — they are refused with 422 before streaming."""
    client = _client(["ok"])
    bodies: list[dict[str, Any]] = [
        {},
        {"messages": []},
        {"messages": [{"role": "user", "parts": []}]},
    ]
    for body in bodies:
        res = client.post("/assistant/chat", json=body)
        assert res.status_code == 422, body


def test_chat_traces_with_the_current_user_and_conversation_id() -> None:
    """The stream is traced under the authenticated therapist + the useChat chat id."""
    tracer = _RecordingTracer()
    service = AssistantService(client=_FakeAssistant(["ok"]), tracer=tracer)
    app.dependency_overrides[get_assistant_service] = lambda: service

    res = TestClient(app).post("/assistant/chat", json={"id": "conv-1", **_BODY})

    assert res.status_code == 200
    assert tracer.calls == [(str(TEST_USER.user_id), "conv-1")]


# --- End-to-end: the REAL tool loop through the endpoint (discover runs once) -------
#
# The fakes above replace the whole client, so they never exercise the discover_api
# tool loop. These wire the real OpenAIAssistant to a fake OpenAI SDK and drive it
# through POST /assistant/chat, so the full path — request body → to_openai_messages
# replay → tool loop → the messages/tools sent to OpenAI — is covered deterministically.


class _FakeSDKStream:
    def __init__(self, chunks: list[SimpleNamespace]) -> None:
        self._chunks = chunks

    def __aiter__(self) -> "_FakeSDKStream":
        self._it = iter(self._chunks)
        return self

    async def __anext__(self) -> SimpleNamespace:
        try:
            return next(self._it)
        except StopIteration:
            raise StopAsyncIteration from None

    async def close(self) -> None: ...


class _FakeSDKCompletions:
    def __init__(self, rounds: list[list[SimpleNamespace]]) -> None:
        self._rounds = list(rounds)
        self.calls: list[dict[str, Any]] = []

    async def create(self, **kwargs: Any) -> _FakeSDKStream:
        self.calls.append(kwargs)
        return _FakeSDKStream(self._rounds.pop(0))


class _FakeSDK:
    def __init__(self, rounds: list[list[SimpleNamespace]]) -> None:
        self.completions = _FakeSDKCompletions(rounds)
        self.chat = SimpleNamespace(completions=self.completions)


def _text_chunk(content: str | None, finish: str | None = None) -> SimpleNamespace:
    delta = SimpleNamespace(content=content, tool_calls=None)
    return SimpleNamespace(choices=[SimpleNamespace(delta=delta, finish_reason=finish)])


def _tool_chunk(call_id: str, name: str) -> SimpleNamespace:
    fn = SimpleNamespace(name=name, arguments="{}")
    tc = SimpleNamespace(index=0, id=call_id, function=fn)
    delta = SimpleNamespace(content=None, tool_calls=[tc])
    return SimpleNamespace(choices=[SimpleNamespace(delta=delta, finish_reason="tool_calls")])


def test_discover_api_runs_once_across_turns_through_the_real_endpoint() -> None:
    async def _fetch(
        url: str, *, headers: dict[str, str], params: dict[str, str] | None = None
    ) -> tuple[int, Any]:
        return 200, {"paths": {"/assistant/context/agenda": {"get": {"summary": "a"}}}}

    # Turn 1: model discovers, then answers. Turn 2: answers straight away.
    sdk = _FakeSDK(
        [
            [_tool_chunk("c1", "discover_api")],
            [_text_chunk("מצאתי", finish="stop")],
            [_text_chunk("הנה מחר", finish="stop")],
        ]
    )
    assistant = OpenAIAssistant(
        client=sdk, model="gpt-4o", tools=Tools(base_url="http://api", fetch=_fetch)
    )
    app.dependency_overrides[get_assistant_service] = lambda: AssistantService(client=assistant)
    client = TestClient(app)

    turn1 = {"messages": [{"role": "user", "parts": [{"type": "text", "text": "מי הבא?"}]}]}
    assert client.post("/assistant/chat", json=turn1).status_code == 200

    # Turn 2 re-sends the conversation, including the assistant's discover_api tool part.
    turn2 = {
        "messages": [
            {"role": "user", "parts": [{"type": "text", "text": "מי הבא?"}]},
            {
                "role": "assistant",
                "parts": [
                    {
                        "type": "tool-discover_api",
                        "toolCallId": "c1",
                        "state": "output-available",
                        "input": {},
                        "output": {"endpoints": [{"path": "/assistant/context/agenda"}]},
                    },
                    {"type": "text", "text": "מצאתי"},
                ],
            },
            {"role": "user", "parts": [{"type": "text", "text": "ומחר?"}]},
        ]
    }
    assert client.post("/assistant/chat", json=turn2).status_code == 200

    offered = [
        {t["function"]["name"] for t in call.get("tools", [])} for call in sdk.completions.calls
    ]
    assert "discover_api" in offered[0]  # turn 1 could discover
    assert "discover_api" not in offered[-1]  # turn 2 must not — already in context
    assert "http_get" in offered[-1]  # but can still fetch, reusing the endpoints


def test_chat_returns_503_when_the_assistant_is_not_configured() -> None:
    """With no OPENAI_API_KEY, the real dependency refuses (forced, not env-dependent)."""
    app.dependency_overrides[get_settings] = lambda: Settings(
        openai_api_key=None,
        database_url=None,
        enable_security=False,
        auth_token_secret_key=None,
    )
    res = TestClient(app).post("/assistant/chat", json=_BODY)

    assert res.status_code == 503
