"""Request models for the chat endpoint and the mapping to OpenAI messages.

The shapes mirror what ``@ai-sdk/react``'s ``useChat`` POSTs: ``{ messages: [...] }``
where each message is a ``UIMessage`` — ``{ id, role, parts: [{ type, text }, ...] }``.
We read text parts and **finished tool parts** (a prior ``discover_api`` / ``http_get``
call the client re-sends), replaying the latter as OpenAI ``tool_calls`` + ``tool``
results so the model reuses earlier discovery instead of repeating it; other part kinds
(files) and extra envelope fields (``id``, ``trigger``) are tolerated and ignored.

Trust note: this endpoint is stateless — the whole conversation, including prior
assistant turns and their tool results, is client-owned and re-POSTed each request. That
trust boundary predates tool replay (assistant *text* was always client-supplied); tool
replay merely lets that same client-owned history include ``tool``-role results. Making
tool results tamper-proof would require server-side session state, which is out of scope.
"""

import json
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

# Roles accepted from the client. "system" is intentionally excluded — the trusted
# system prompt is prepended server-side, so a client-supplied system message could
# only be an attempt to override the assistant's guardrails.
_ALLOWED_ROLES = {"user", "assistant"}

# Boundary caps, mirroring the codebase convention (auth/patients schemas). Keep the
# request bounded so a caller cannot forward an unbounded payload to OpenAI.
_MAX_TEXT_CHARS = 8_000
_MAX_PARTS_PER_MESSAGE = 50
_MAX_MESSAGES = 100


class ChatPart(BaseModel):
    """One part of a UIMessage. We read text parts and completed tool parts; the rest
    are ignored.

    A tool part is how the AI-SDK re-sends an earlier ``discover_api`` / ``http_get``
    call so the model can reuse it. Its ``type`` is ``tool-<name>`` (statically typed
    tools) or ``dynamic-tool`` (then the name is in ``tool_name``); ``state`` is
    ``output-available`` once the result is in.
    """

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    type: str
    text: str | None = Field(default=None, max_length=_MAX_TEXT_CHARS)
    tool_call_id: str | None = Field(default=None, alias="toolCallId")
    tool_name: str | None = Field(default=None, alias="toolName")
    state: str | None = None
    input: Any = None
    output: Any = None

    def tool_name_of(self) -> str | None:
        """The tool's name if this is a tool part, else ``None``."""
        if self.type.startswith("tool-"):
            return self.type[len("tool-") :]
        if self.type == "dynamic-tool":
            return self.tool_name
        return None

    def is_completed_tool(self) -> bool:
        """True when this is a tool call that finished (has an id and an output) — the
        only kind we replay, since OpenAI requires every tool_call id to have a reply."""
        return (
            self.tool_name_of() is not None
            and bool(self.tool_call_id)
            and self.state == "output-available"
        )


class ChatMessage(BaseModel):
    """A single UIMessage from the conversation."""

    model_config = ConfigDict(extra="ignore")

    role: str
    parts: list[ChatPart] = Field(default_factory=list, max_length=_MAX_PARTS_PER_MESSAGE)

    def text(self) -> str:
        """Concatenate this message's text parts into a single content string."""
        return "".join(part.text for part in self.parts if part.type == "text" and part.text)

    def completed_tools(self) -> list[ChatPart]:
        """The finished tool calls in this message, in order (empty for user turns)."""
        return [part for part in self.parts if part.is_completed_tool()]


# Bound the conversation id: it is only a tracing/grouping label, never trusted.
_MAX_ID_CHARS = 200


class ChatRequest(BaseModel):
    """The body useChat sends to ``POST /assistant/chat``."""

    model_config = ConfigDict(extra="ignore")

    # useChat sends a stable per-conversation ``id``; we use it only to group a
    # conversation's turns into one tracing session. Optional and untrusted.
    id: str | None = Field(default=None, max_length=_MAX_ID_CHARS)
    messages: list[ChatMessage] = Field(default_factory=list, max_length=_MAX_MESSAGES)


def session_id(request: ChatRequest) -> str | None:
    """The conversation id to group tracing by, or ``None`` when absent/blank."""
    return (request.id or "").strip() or None


def latest_question_length(request: ChatRequest) -> int:
    """Character length of the most recent user question (0 if there is none)."""
    for message in reversed(request.messages):
        if message.role == "user":
            return len(message.text())
    return 0


def to_openai_messages(request: ChatRequest, system_prompt: str) -> list[dict[str, Any]]:
    """Build the OpenAI message list: the system prompt followed by the conversation.

    Assistant turns replay their finished tool calls (``discover_api`` / ``http_get``)
    as ``assistant.tool_calls`` + matching ``tool`` messages, so the model sees it has
    already discovered/fetched and does not repeat those calls every prompt. The shapes
    mirror the live tool loop in ``assistant/client.py``.

    Messages with an unsupported role or no usable content are dropped, so an empty or
    malformed history yields just the system prompt rather than an API error.
    """
    messages: list[dict[str, Any]] = [{"role": "system", "content": system_prompt}]
    for message in request.messages:
        if message.role not in _ALLOWED_ROLES:
            continue
        if message.role == "user":
            content = message.text()
            if content:
                messages.append({"role": "user", "content": content})
            continue

        # Assistant turn: emit its tool round(s) first (calls immediately followed by
        # their results, as OpenAI requires), then the final answer text.
        tools = message.completed_tools()
        if tools:
            messages.append(
                {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": part.tool_call_id,
                            "type": "function",
                            "function": {
                                "name": part.tool_name_of(),
                                "arguments": json.dumps(part.input or {}, ensure_ascii=False),
                            },
                        }
                        for part in tools
                    ],
                }
            )
            for part in tools:
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": part.tool_call_id,
                        "content": json.dumps(part.output, ensure_ascii=False),
                    }
                )
        text = message.text()
        if text:
            messages.append({"role": "assistant", "content": text})
    return messages
