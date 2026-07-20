"""Invariants for the assistant system prompt.

Behaviour is LLM-driven, so we can't unit-test the model's refusals directly; we
instead lock in the guardrail *language* that produces them. If someone weakens the
domain-scope / tool-grounding rules, these fail. Whitespace is normalised so the
assertions survive re-wrapping of the Hebrew source.
"""

from assistant.prompt import ASSISTANT_SYSTEM_PROMPT

_NORMALIZED = " ".join(ASSISTANT_SYSTEM_PROMPT.split())


def test_prompt_restricts_answers_to_the_system_domain() -> None:
    # Refuses general-knowledge / off-topic questions.
    assert "תחום המענה ומקורות המידע" in _NORMALIZED
    assert "עונים אך ורק על נושאים הקשורים למערכת" in _NORMALIZED
    assert "איני עונה על שאלות כלליות" in _NORMALIZED


def test_prompt_grounds_facts_only_in_tool_results() -> None:
    # Facts about the practice come only from tool calls, never the model's knowledge.
    assert "הסתמכו אך ורק על נתונים שהוחזרו מקריאות כלים" in _NORMALIZED
    assert "אל תשתמשו בידע מוקדם" in _NORMALIZED


def test_prompt_has_no_emoji() -> None:
    # Product-wide rule: no emoji in UI/output.
    assert all(ord(ch) < 0x1F000 for ch in ASSISTANT_SYSTEM_PROMPT)
