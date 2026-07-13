"""Parse Ollama output into structured next-meeting report fields."""

from __future__ import annotations

import json
import re
from typing import Any

INTRO_HEADING = "## סקירה מהירה"
CHANGES_HEADING = "## שינויים ומגמות"
OPEN_HEADING = "## נושאים פתוחים לפגישה הבאה"
FOLLOWUP_HEADING = "## המשך ומעקב"

_SECTION_ORDER = (INTRO_HEADING, CHANGES_HEADING, OPEN_HEADING)

_HEADING_ALIASES: dict[str, str] = {
    INTRO_HEADING: INTRO_HEADING,
    "## סקירה": INTRO_HEADING,
    CHANGES_HEADING: CHANGES_HEADING,
    "## מה השתנה": CHANGES_HEADING,
    "## מגמות": CHANGES_HEADING,
    OPEN_HEADING: OPEN_HEADING,
    "## נושאים פתוחים": OPEN_HEADING,
    "## נושאים להמשך": OPEN_HEADING,
}


def _compact(s: str) -> str:
    return s.replace(" ", "")


def _normalize_heading(line: str) -> str | None:
    stripped = line.strip()
    compact = _compact(stripped)
    for alias, canonical in _HEADING_ALIASES.items():
        if stripped == alias or compact == _compact(alias):
            return canonical
    return None


def extract_bullets(body: str) -> list[str]:
    items: list[str] = []
    for raw in body.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith(("- ", "* ", "• ")):
            items.append(line[2:].strip())
        elif line[:1].isdigit() and "." in line[:4]:
            after = line.split(".", 1)[1].strip()
            if after:
                items.append(after)
    return items


def bullets_under_heading(text: str, heading: str) -> list[str]:
    lines = text.splitlines()
    body: list[str] = []
    in_section = False
    target = _compact(heading.strip())
    for raw in lines:
        line = raw.strip()
        if line.startswith("## "):
            in_section = _compact(line) == target or heading.strip() in line
            continue
        if not in_section:
            continue
        body.append(raw)
    return extract_bullets("\n".join(body))


def _strip_fences(raw: str) -> str:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, count=1, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text, count=1)
    return text.strip()


def _as_str_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip()
    return [text] if text else []


def parse_report_json(text: str) -> tuple[str, list[str], list[str]] | None:
    cleaned = _strip_fences(text)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start < 0 or end <= start:
            return None
        try:
            data = json.loads(cleaned[start : end + 1])
        except json.JSONDecodeError:
            return None
    if not isinstance(data, dict):
        return None
    intro = str(data.get("intro") or "").strip()
    changes = _as_str_list(data.get("changes"))
    open_topics = _as_str_list(data.get("open_topics"))
    if not intro and not changes and not open_topics:
        return None
    return intro, changes, open_topics


def parse_report_markdown(text: str) -> tuple[str, list[str], list[str]]:
    sections: dict[str, list[str]] = {h: [] for h in _SECTION_ORDER}
    current: str | None = None

    for line in text.splitlines():
        heading = _normalize_heading(line)
        if heading is not None:
            current = heading
            continue
        if current is None:
            continue
        sections[current].append(line)

    if not any(sections[h] for h in _SECTION_ORDER) and INTRO_HEADING not in text:
        return text.strip(), [], []

    intro = "\n".join(sections[INTRO_HEADING]).strip()
    changes = extract_bullets("\n".join(sections[CHANGES_HEADING]))
    open_topics = extract_bullets("\n".join(sections[OPEN_HEADING]))

    if not intro and not changes and not open_topics:
        return text.strip(), [], []

    return intro, changes, open_topics


def parse_report_output(text: str) -> tuple[str, list[str], list[str]]:
    """Prefer JSON; fall back to markdown headings for older model replies."""
    parsed = parse_report_json(text)
    if parsed is not None:
        return parsed
    return parse_report_markdown(text)
