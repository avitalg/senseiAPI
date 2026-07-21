from collections.abc import AsyncIterator, Iterator, Sequence
from contextlib import contextmanager
from typing import Any

import pytest

from assistant.client import (
    AssistantClient,
    AssistantError,
    StreamEvent,
    TextChunk,
    ToolCallChunk,
    ToolResultChunk,
)
from assistant.prompt import ASSISTANT_SYSTEM_PROMPT
from assistant.schemas import ChatRequest
from assistant.service import AssistantService
from assistant.tracing import ChatTrace, Tracer


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class _RecordingTrace(ChatTrace):
    def __init__(self) -> None:
        self.output: str | None = None
        self.error: str | None = None

    def set_output(self, text: str) -> None:
        self.output = text

    def set_error(self, message: str) -> None:
        self.error = message


class _RecordingTracer(Tracer):
    def __init__(self) -> None:
        self.calls: list[tuple[str | None, str | None]] = []
        self.trace = _RecordingTrace()

    @contextmanager
    def trace_chat(self, *, user_id: str | None, session_id: str | None) -> Iterator[ChatTrace]:
        self.calls.append((user_id, session_id))
        yield self.trace


class _FakeAssistant(AssistantClient):
    def __init__(self, events: list[StreamEvent], error: str | None = None) -> None:
        self._events = events
        self._error = error
        self.seen: list[dict[str, Any]] | None = None

    async def stream(self, messages: Sequence[dict[str, Any]]) -> AsyncIterator[StreamEvent]:
        self.seen = list(messages)
        for event in self._events:
            yield event
        if self._error is not None:
            raise AssistantError(self._error)


def _request(text: str) -> ChatRequest:
    return ChatRequest.model_validate(
        {"messages": [{"role": "user", "parts": [{"type": "text", "text": text}]}]}
    )


@pytest.mark.anyio
async def test_stream_sse_emits_the_full_text_sequence() -> None:
    service = AssistantService(client=_FakeAssistant([TextChunk("שלום"), TextChunk(" עולם")]))

    frames = [f async for f in service.stream_sse(_request("היי"))]
    body = "".join(frames)

    assert '"type":"start"' in body
    assert '"type":"text-start"' in body
    assert '"delta":"שלום"' in body and '"delta":" עולם"' in body
    assert '"type":"text-end"' in body
    assert '"type":"finish"' in body
    assert frames[-1] == "data: [DONE]\n\n"


@pytest.mark.anyio
async def test_stream_sse_emits_tool_parts_before_text() -> None:
    events: list[StreamEvent] = [
        ToolCallChunk(id="c1", name="http_get", arguments={"path": "/assistant/context/agenda"}),
        ToolResultChunk(id="c1", name="http_get", output={"status": 200, "body": []}),
        TextChunk("אין פגישות."),
    ]
    service = AssistantService(client=_FakeAssistant(events))

    frames = [f async for f in service.stream_sse(_request("מי הבא?"))]
    body = "".join(frames)

    assert '"type":"tool-input-available"' in body
    assert '"toolName":"http_get"' in body
    assert '"type":"tool-output-available"' in body
    # Tool parts precede the text answer.
    assert body.index("tool-input-available") < body.index("text-delta")
    assert frames[-1] == "data: [DONE]\n\n"


@pytest.mark.anyio
async def test_stream_sse_prepends_the_system_prompt() -> None:
    client = _FakeAssistant([TextChunk("ok")])
    service = AssistantService(client=client)

    [f async for f in service.stream_sse(_request("היי"))]

    assert client.seen is not None
    assert client.seen[0] == {"role": "system", "content": ASSISTANT_SYSTEM_PROMPT}
    assert client.seen[1] == {"role": "user", "content": "היי"}


@pytest.mark.anyio
async def test_stream_sse_replays_prior_tool_calls_to_the_client() -> None:
    """A second turn whose history carries a finished discover_api call reaches the
    client as an assistant.tool_calls + tool result pair, so the model can reuse the
    earlier discovery instead of calling it again."""
    client = _FakeAssistant([TextChunk("מחרתיים אין פגישות.")])
    service = AssistantService(client=client)
    request = ChatRequest.model_validate(
        {
            "messages": [
                {"role": "user", "parts": [{"type": "text", "text": "מי הבא?"}]},
                {
                    "role": "assistant",
                    "parts": [
                        {
                            "type": "tool-discover_api",
                            "toolCallId": "call_1",
                            "state": "output-available",
                            "input": {},
                            "output": {"endpoints": [{"path": "/assistant/context/agenda"}]},
                        },
                        {"type": "text", "text": "מחר יש פגישה."},
                    ],
                },
                {"role": "user", "parts": [{"type": "text", "text": "ומחרתיים?"}]},
            ]
        }
    )

    [f async for f in service.stream_sse(request)]

    assert client.seen is not None
    roles = [m["role"] for m in client.seen]
    assert roles == ["system", "user", "assistant", "tool", "assistant", "user"]
    assert client.seen[2]["tool_calls"][0]["function"]["name"] == "discover_api"
    assert client.seen[3]["tool_call_id"] == "call_1"


@pytest.mark.anyio
async def test_stream_sse_reports_a_mid_stream_error() -> None:
    service = AssistantService(client=_FakeAssistant([TextChunk("חלק ")], error="overloaded"))

    frames = [f async for f in service.stream_sse(_request("היי"))]
    body = "".join(frames)

    assert '"type":"error"' in body and "overloaded" in body
    assert '"type":"finish"' not in body
    assert frames[-1] == "data: [DONE]\n\n"


@pytest.mark.anyio
async def test_stream_sse_traces_the_request_with_user_and_session() -> None:
    tracer = _RecordingTracer()
    service = AssistantService(
        client=_FakeAssistant([TextChunk("שלום"), TextChunk(" עולם")]), tracer=tracer
    )

    [f async for f in service.stream_sse(_request("היי"), user_id="u1", session_id="s1")]

    assert tracer.calls == [("u1", "s1")]
    assert tracer.trace.output == "שלום עולם"
    assert tracer.trace.error is None


@pytest.mark.anyio
async def test_stream_sse_records_a_mid_stream_error_on_the_trace() -> None:
    tracer = _RecordingTracer()
    service = AssistantService(
        client=_FakeAssistant([TextChunk("חלק ")], error="overloaded"), tracer=tracer
    )

    [f async for f in service.stream_sse(_request("היי"), user_id="u1", session_id="s1")]

    assert tracer.trace.error == "overloaded"
    assert tracer.trace.output is None
