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


def summary_json_to_markdown(data: dict[str, Any]) -> str:
    """Render structured summary JSON into the Hebrew ## sections the UI expects."""
    topics = _as_str(data.get("main_topics") or data.get("topics"))
    interventions = _as_str(
        data.get("therapist_interventions") or data.get("interventions")
    )
    risk = _as_str(data.get("risk_signs") or data.get("risk"))
    follow = _as_str_list(data.get("follow_up") or data.get("followup"))
    follow_block = "\n".join(f"- {item}" for item in follow) if follow else "לא עלה בפגישה"

    return (
        "## נושאים מרכזיים\n"
        f"{topics or 'לא עלה בפגישה'}\n\n"
        "## התערבויות המטפל/ת\n"
        f"{interventions or 'לא עלה בפגישה'}\n\n"
        "## סימני סיכון\n"
        f"{risk or 'לא נאמרו אמירות מפורשות של סיכון'}\n\n"
        "## המשך ומעקב\n"
        f"{follow_block}"
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


def _looks_like_summary(data: dict[str, Any]) -> bool:
    return bool(_SUMMARY_KEYS.intersection(data.keys()))


def _extract_json_dict(cleaned: str) -> dict[str, Any] | None:
    """Parse a summary dict from model text, preferring the last valid object.

    Models sometimes emit broken outer JSON and a clean nested object — walk ``{``
    candidates from the end so we still recover structured fields.
    """
    try:
        data = json.loads(cleaned)
        if isinstance(data, dict) and _looks_like_summary(data):
            return data
    except json.JSONDecodeError:
        pass

    end = cleaned.rfind("}")
    if end < 0:
        return None
    # Prefer later (nested) objects when the outer wrapper is broken.
    for start in range(end, -1, -1):
        if cleaned[start] != "{":
            continue
        try:
            data = json.loads(cleaned[start : end + 1])
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict) and _looks_like_summary(data):
            return data
    return None


def normalize_summary_output(raw: str) -> str:
    """Prefer JSON → markdown; if not JSON, keep the raw model text."""
    cleaned = _strip_fences(raw)
    data = _extract_json_dict(cleaned)
    if data is None:
        return raw.strip()
    return summary_json_to_markdown(data)
