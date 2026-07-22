"""Token counting + history trimming, to keep the prompt under a token ceiling.

Uses ``tiktoken`` (OpenAI's tokenizer) when available, falling back to a rough
character estimate so it never breaks offline. The counter is injectable so tests
stay hermetic (no tokenizer download).
"""

from collections.abc import Callable, Sequence
from typing import Any

# Small fixed overhead per chat message (role/formatting), matching OpenAI's guidance.
_PER_MESSAGE_TOKENS = 4

_counter: Callable[[str], int] | None = None


def _build_counter() -> Callable[[str], int]:
    try:
        import tiktoken

        # o200k_base is the encoding for the GPT-4o / GPT-5 families.
        encoding = tiktoken.get_encoding("o200k_base")
        return lambda text: len(encoding.encode(text))
    except Exception:
        # Rough fallback (~4 chars/token) if tiktoken is unavailable/offline.
        return lambda text: max(1, len(text) // 4)


def count_tokens(text: str) -> int:
    global _counter
    if _counter is None:
        _counter = _build_counter()
    return _counter(text)


def _message_tokens(message: dict[str, Any], count: Callable[[str], int]) -> int:
    content = message.get("content")
    total = count(content if isinstance(content, str) else "")
    # tool_calls carry their payload in a structured field, not `content` — count it so
    # a history full of replayed tool calls is not badly under-counted against the budget.
    for call in message.get("tool_calls") or []:
        function = call.get("function") or {}
        total += count(function.get("name") or "") + count(function.get("arguments") or "")
    return total + _PER_MESSAGE_TOKENS


def _tool_sequence_blocks(tail: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    """Group the conversation into atomic blocks, keeping each ``assistant`` message's
    ``tool_calls`` together with the ``tool`` result messages that immediately follow it.

    Trimming operates on whole blocks so it can never split a tool sequence — which would
    leave OpenAI either an orphan ``tool`` message or an ``assistant.tool_calls`` with no
    reply, both of which it rejects. Every other message is its own single-item block.
    """
    blocks: list[list[dict[str, Any]]] = []
    i = 0
    while i < len(tail):
        message = tail[i]
        if message.get("role") == "assistant" and message.get("tool_calls"):
            j = i + 1
            while j < len(tail) and tail[j].get("role") == "tool":
                j += 1
            blocks.append(tail[i:j])
            i = j
        else:
            blocks.append([message])
            i += 1
    return blocks


def trim_to_token_budget(
    messages: Sequence[dict[str, Any]],
    max_tokens: int,
    *,
    count: Callable[[str], int] = count_tokens,
) -> list[dict[str, Any]]:
    """Drop the oldest messages until the prompt fits ``max_tokens``.

    The leading system message and the most recent turn are always kept, so trimming
    never removes the guardrails or the live turn. Tool sequences (an ``assistant``
    ``tool_calls`` message plus its ``tool`` results) are kept or dropped as one unit,
    so the result is always a valid OpenAI message list.
    """
    messages = list(messages)
    if not messages:
        return messages

    head = messages[:1] if messages[0].get("role") == "system" else []
    tail = messages[len(head) :]

    budget = max_tokens - sum(_message_tokens(m, count) for m in head)
    kept_blocks: list[list[dict[str, Any]]] = []
    for block in reversed(_tool_sequence_blocks(tail)):
        cost = sum(_message_tokens(m, count) for m in block)
        if kept_blocks and cost > budget:
            break  # keep at least the latest block, then stop once full
        budget -= cost
        kept_blocks.append(block)
    kept_blocks.reverse()
    return head + [message for block in kept_blocks for message in block]
