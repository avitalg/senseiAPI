from typing import Any

from assistant.tokens import trim_to_token_budget


# Deterministic 1-token-per-char counter so the tests need no real tokenizer.
def _count(text: str) -> int:
    return len(text)


def _msg(role: str, char: str, n: int) -> dict[str, Any]:
    return {"role": role, "content": char * n}


def test_no_trim_when_under_budget() -> None:
    messages = [_msg("system", "S", 5), _msg("user", "a", 5)]
    assert trim_to_token_budget(messages, 10_000, count=_count) == messages


def test_drops_oldest_history_but_keeps_system_and_latest() -> None:
    messages = [
        _msg("system", "S", 10),
        _msg("user", "a", 10),  # oldest — should be dropped
        _msg("assistant", "b", 10),
        _msg("user", "c", 10),  # latest — must survive
    ]

    trimmed = trim_to_token_budget(messages, max_tokens=40, count=_count)

    firsts = [m["content"][0] for m in trimmed]
    assert firsts[0] == "S"  # system kept at the front
    assert "c" in firsts  # latest question kept
    assert "a" not in firsts  # oldest dropped to fit the budget


def test_keeps_latest_message_even_if_it_exceeds_the_budget() -> None:
    messages = [_msg("system", "S", 1), _msg("user", "x", 100)]

    trimmed = trim_to_token_budget(messages, max_tokens=1, count=_count)

    assert trimmed[-1]["content"] == "x" * 100  # never drop the live turn


def _tool_call_msg(call_id: str, args_len: int) -> dict[str, Any]:
    return {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {
                "id": call_id,
                "type": "function",
                "function": {"name": "n", "arguments": "a" * args_len},
            }
        ],
    }


def test_drops_orphan_leading_tool_message_when_its_tool_calls_is_trimmed() -> None:
    """Trimming keeps newest-first, so it can keep a `tool` result while dropping the
    `assistant` message whose `tool_calls` introduced it. That orphan `tool` message is
    an OpenAI error, so it must be dropped from the head of the kept slice."""
    messages = [
        _msg("system", "S", 5),
        _tool_call_msg("c1", 30),  # costly → gets trimmed out
        _msg("tool", "r", 5),  # its result — would be left orphaned at the head
        _msg("user", "c", 5),  # latest — must survive
    ]

    trimmed = trim_to_token_budget(messages, max_tokens=30, count=_count)

    roles = [m["role"] for m in trimmed]
    assert roles == ["system", "user"]  # orphan `tool` dropped, no dangling tool_calls


def test_keeps_the_newest_tool_sequence_whole_when_it_is_the_live_turn() -> None:
    """History can end in an `assistant` tool_calls + `tool` result with no trailing user
    message (an AI-SDK regenerate). The newest tool sequence must be kept as one unit —
    never split into an orphan `tool`, and never trimmed away leaving just the system
    prompt (which would send OpenAI an empty conversation)."""
    messages = [
        _msg("system", "S", 5),
        _msg("user", "a", 50),  # older question — trimmed out
        _tool_call_msg("c1", 5),
        _msg("tool", "r", 5),  # newest — its owning tool_calls must be kept with it
    ]

    trimmed = trim_to_token_budget(messages, max_tokens=15, count=_count)

    roles = [m["role"] for m in trimmed]
    assert roles == ["system", "assistant", "tool"]  # whole sequence kept, nothing orphaned
    assert trimmed[1]["tool_calls"][0]["id"] == "c1"


def test_counts_tool_call_arguments_toward_the_budget() -> None:
    # Two assistant tool_calls messages of equal argument size; with a budget that fits
    # only one, the older is dropped — proving the args (not just `content`) are counted.
    messages = [
        _msg("system", "S", 1),
        _tool_call_msg("old", 20),
        _msg("tool", "r", 1),
        _tool_call_msg("new", 20),
        _msg("tool", "r", 1),
        _msg("user", "q", 1),
    ]

    trimmed = trim_to_token_budget(messages, max_tokens=40, count=_count)

    call_ids = [c["id"] for m in trimmed if m.get("tool_calls") for c in m["tool_calls"]]
    assert "new" in call_ids and "old" not in call_ids
