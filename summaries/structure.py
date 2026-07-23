"""Split a rendered Hebrew session summary into its labelled sections.

Two markdown dialects reach this module and both must parse:

* seeded demo summaries (``seeds/patients/*.json``) use fully-bold headings —
  ``**תובנות מרכזיות**`` — preceded by a title line and a ``·``-separated meta line;
* live model output rendered by :mod:`summaries.format` uses ``## תובנות מרכזיות``
  and carries no title lines.

The flat ``text`` stays the source of truth; this is a convenience view for clients
that want to render the sections separately. Anything unrecognised is left in the
section it appeared under rather than dropped.
"""

from __future__ import annotations

import re

from pydantic import BaseModel

from summaries.format import as_bullet_items

# Heading label -> field. Both dialects share one table; labels are matched after
# stripping markers, so `## נושאים מרכזיים` and `**נושאים מרכזיים**` land together.
_HEADINGS: dict[str, str] = {
    "תובנות מרכזיות": "insights",
    "תובנות": "insights",
    "סיכום הפגישה": "session_summary",
    "סיכום המפגש": "session_summary",
    "נושאים מרכזיים": "session_main_topics",
    "דגלי סיכון": "session_risk_flags",
    "סימני סיכון": "session_risk_flags",
    # Live-only sections; seeded summaries carry neither, so both stay empty there.
    "התערבויות המטפל/ת": "therapist_interventions",
    "התערבויות המטפל": "therapist_interventions",
    "המשך ומעקב": "follow_up",
}

_ATX_HEADING = re.compile(r"^#{1,6}\s*(?P<label>.+?)\s*$")
_BOLD_HEADING = re.compile(r"^\*\*(?P<label>[^*]+)\*\*\s*$")

# Inside the risk block: the italic parenthesised disclaimer, the bold severity
# word followed by its note, and the optional nested "לתשומת לב" subsection.
_DISCLAIMER = re.compile(r"^\*\((?P<text>.+?)\)\*\s*$", re.MULTILINE)
_LEVEL_AND_NOTE = re.compile(r"^\*\*(?P<level>[^*]+)\*\*\s*[—–-]\s*(?P<note>.*)$", re.DOTALL)
_ATTENTION_HEADING = re.compile(r"^\*\*לתשומת לב\*\*\s*$", re.MULTILINE)


class SummaryRiskFlags(BaseModel):
    """The risk section, split into its parts. Every part is optional.

    An indicator the therapist reviews — never a diagnosis, and never a
    substitute for reading the transcript.
    """

    level: str | None = None
    note: str | None = None
    attention: str | None = None
    disclaimer: str | None = None


class StructuredSummary(BaseModel):
    """A rendered summary split by heading. Absent sections stay empty."""

    title: str | None = None
    subtitle: str | None = None
    insights: str | None = None
    session_summary: str | None = None
    session_main_topics: list[str] = []
    session_risk_flags: SummaryRiskFlags | None = None
    therapist_interventions: list[str] = []
    follow_up: list[str] = []


def _heading_field(line: str) -> str | None:
    """Return the field a heading line maps to, or None if it is not a heading.

    A bold line that is not a known heading (``**לתשומת לב**``) is content, not a
    section break, so it stays with the section it was written under.
    """
    for pattern in (_ATX_HEADING, _BOLD_HEADING):
        match = pattern.match(line)
        if match is None:
            continue
        label = match.group("label").strip().strip("*").rstrip(":").strip()
        field = _HEADINGS.get(label)
        if field is not None:
            return field
    return None


def _split_sections(text: str) -> tuple[list[str], dict[str, str]]:
    """Split into the lines before the first heading and a field -> body map."""
    preamble: list[str] = []
    sections: dict[str, list[str]] = {}
    current: str | None = None

    for line in text.splitlines():
        field = _heading_field(line)
        if field is not None:
            current = field
            sections.setdefault(current, [])
            continue
        if current is None:
            preamble.append(line)
        else:
            sections[current].append(line)

    bodies = {field: "\n".join(lines).strip() for field, lines in sections.items()}
    return [line.strip() for line in preamble if line.strip()], bodies


def _parse_risk_flags(block: str) -> SummaryRiskFlags | None:
    """Pull disclaimer, severity level, note and follow-up attention out of the block."""
    if not block.strip():
        return None

    disclaimer_match = _DISCLAIMER.search(block)
    disclaimer = disclaimer_match.group("text").strip() if disclaimer_match else None
    body = _DISCLAIMER.sub("", block).strip()

    attention: str | None = None
    parts = _ATTENTION_HEADING.split(body, maxsplit=1)
    if len(parts) == 2:
        body = parts[0].strip()
        attention = parts[1].strip() or None

    level: str | None = None
    note: str | None = body or None
    level_match = _LEVEL_AND_NOTE.match(body)
    if level_match is not None:
        level = level_match.group("level").strip() or None
        note = level_match.group("note").strip() or None

    flags = SummaryRiskFlags(level=level, note=note, attention=attention, disclaimer=disclaimer)
    if flags.model_dump(exclude_none=True):
        return flags
    return None


def parse_summary_sections(text: str) -> StructuredSummary | None:
    """Split a rendered summary into sections, or None when no section is recognised.

    Returning None keeps an unparseable blob non-fatal: the caller still serves the
    flat ``text`` and reports the structured view as absent.
    """
    if not text.strip():
        return None

    preamble, bodies = _split_sections(text)
    if not bodies:
        return None

    risk_block = bodies.get("session_risk_flags", "")
    return StructuredSummary(
        title=preamble[0] if preamble else None,
        subtitle="\n".join(preamble[1:]) or None,
        insights=bodies.get("insights") or None,
        session_summary=bodies.get("session_summary") or None,
        session_main_topics=as_bullet_items(bodies.get("session_main_topics")),
        session_risk_flags=_parse_risk_flags(risk_block),
        therapist_interventions=as_bullet_items(bodies.get("therapist_interventions")),
        follow_up=as_bullet_items(bodies.get("follow_up")),
    )
