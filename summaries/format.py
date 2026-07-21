"""Parse and normalize session-summary model output (JSON preferred)."""

from __future__ import annotations

import json
import re
from typing import Any


def _strip_fences(raw: str) -> str:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, count=1, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text, count=1)
    return text.strip()


def _as_str(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return "\n".join(f"- {str(item).strip()}" for item in value if str(item).strip())
    return str(value).strip()


def _as_str_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip()
    return [text] if text else []


# Split prose into discrete items: on newlines, list separators, and sentence
# terminators. Models return `main_topics`/`interventions` as free text, so this
# turns a paragraph into scannable bullets instead of one giant line.
_SEGMENT_SPLIT = re.compile(r"(?<=[.!?])\s+|[\n;•·]+")
_LEADING_MARKER = re.compile(r"^(?:[-*•·]\s*|\d+[.)]\s*)")


def _as_bullet_items(value: Any) -> list[str]:
    """Coerce a value into discrete items; keep list items, split prose strings."""
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    items: list[str] = []
    for chunk in _SEGMENT_SPLIT.split(str(value)):
        cleaned = _LEADING_MARKER.sub("", chunk.strip()).strip()
        if cleaned:
            items.append(cleaned)
    return items


def _bullet_block(items: list[str], empty: str) -> str:
    return "\n".join(f"- {item}" for item in items) if items else empty


def summary_json_to_markdown(data: dict[str, Any]) -> str:
    """Render structured summary JSON into the Hebrew ## sections the UI expects."""
    topics = _as_bullet_items(data.get("main_topics") or data.get("topics"))
    interventions = _as_bullet_items(
        data.get("therapist_interventions") or data.get("interventions")
    )
    risk = _as_str(data.get("risk_signs") or data.get("risk"))
    follow = _as_str_list(data.get("follow_up") or data.get("followup"))

    return (
        "## נושאים מרכזיים\n"
        f"{_bullet_block(topics, 'לא עלה בפגישה')}\n\n"
        "## התערבויות המטפל/ת\n"
        f"{_bullet_block(interventions, 'לא עלה בפגישה')}\n\n"
        "## סימני סיכון\n"
        f"{risk or 'לא נאמרו אמירות מפורשות של סיכון'}\n\n"
        "## המשך ומעקב\n"
        f"{_bullet_block(follow, 'לא עלה בפגישה')}"
    ).strip()


_SUMMARY_KEYS = frozenset(
    {
        "main_topics",
        "topics",
        "therapist_interventions",
        "interventions",
        "risk_signs",
        "risk",
        "follow_up",
        "followup",
    }
)

# Models often omit commas between adjacent JSON strings (esp. in follow_up arrays).
_MISSING_COMMA_BETWEEN_STRINGS = re.compile(r'"\s*\n\s*"')
_MISSING_COMMA_SAME_LINE = re.compile(r'"\s+"')
_TRAILING_COMMA = re.compile(r",\s*([}\]])")

_STRING_FIELD = re.compile(
    r'"(main_topics|topics|therapist_interventions|interventions|risk_signs|risk)"\s*:\s*"((?:\\.|[^"\\])*)"',
    re.DOTALL,
)
_ARRAY_FIELD = re.compile(
    r'"(follow_up|followup)"\s*:\s*\[(.*?)\]',
    re.DOTALL,
)
_ARRAY_STRING = re.compile(r'"((?:\\.|[^"\\])*)"')


def _looks_like_summary(data: dict[str, Any]) -> bool:
    return bool(_SUMMARY_KEYS.intersection(data.keys()))


def _repair_almost_json(text: str) -> str:
    """Fix common LLM JSON mistakes enough for json.loads to succeed."""
    fixed = _MISSING_COMMA_BETWEEN_STRINGS.sub('",\n"', text)
    fixed = _MISSING_COMMA_SAME_LINE.sub('", "', fixed)
    fixed = _TRAILING_COMMA.sub(r"\1", fixed)
    return fixed


def _unescape_json_string(value: str) -> str:
    try:
        loaded = json.loads(f'"{value}"')
    except json.JSONDecodeError:
        return value.replace('\\"', '"').replace("\\n", "\n").strip()
    return loaded if isinstance(loaded, str) else value


def _salvage_summary_fields(text: str) -> dict[str, Any] | None:
    """Pull summary fields with regex when the blob is not valid JSON."""
    data: dict[str, Any] = {}
    for match in _STRING_FIELD.finditer(text):
        key, raw_val = match.group(1), match.group(2)
        data[key] = _unescape_json_string(raw_val)
    arr = _ARRAY_FIELD.search(text)
    if arr:
        items = [_unescape_json_string(m.group(1)) for m in _ARRAY_STRING.finditer(arr.group(2))]
        data[arr.group(1)] = [item for item in items if item]
    if not _looks_like_summary(data):
        return None
    return data


def _extract_json_dict(cleaned: str) -> dict[str, Any] | None:
    """Parse a summary dict from model text, preferring the last valid object.

    Models sometimes emit broken outer JSON and a clean nested object — walk ``{``
    candidates from the end so we still recover structured fields.
    """
    candidates = [cleaned, _repair_almost_json(cleaned)]
    for candidate in candidates:
        try:
            data = json.loads(candidate)
            if isinstance(data, dict) and _looks_like_summary(data):
                return data
        except json.JSONDecodeError:
            pass

        end = candidate.rfind("}")
        if end < 0:
            continue
        # Prefer later (nested) objects when the outer wrapper is broken.
        for start in range(end, -1, -1):
            if candidate[start] != "{":
                continue
            try:
                data = json.loads(candidate[start : end + 1])
            except json.JSONDecodeError:
                continue
            if isinstance(data, dict) and _looks_like_summary(data):
                return data

    return _salvage_summary_fields(cleaned)


def normalize_summary_output(raw: str) -> str:
    """Prefer JSON → markdown; if not JSON, keep the raw model text."""
    cleaned = _strip_fences(raw)
    data = _extract_json_dict(cleaned)
    if data is None:
        return raw.strip()
    return summary_json_to_markdown(data)
