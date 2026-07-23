"""Parse the Markdown mock-patient files kept in the sensei-patients repo.

Pure text-in/data-out helpers — no filesystem and no network — so they can be
unit-tested against inline fixtures. ``seeds/generate.py`` reads the files and
turns these results into ``seeds/patients/*.json``.

``recorded_sessions.md`` sections look like::

    ## מפגש 1: <title>

    "<dictated therapist recording>"

    🎙️ הקלטת המטפל (Note): "<private clinical note>"

``session_summaries.md`` sections look like::

    ## פגישה 1
    <title>

    <name> · DD/MM/YY · HH:MM · N דק׳

    **תובנות מרכזיות**
    ...
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

ISRAEL_TZ = ZoneInfo("Asia/Jerusalem")

NOTE_MARKER = "🎙️"

# Only spaces and tabs may separate the header parts. ``\s*`` would match a
# newline, so an untitled "## מפגש 1" header would swallow the line below it as
# its title — which is exactly the shape simba's file uses.
_RECORDED_HEADER = re.compile(
    r"^##[ \t]*מפגש[ \t]*(?P<n>\d+)[ \t]*:?[ \t]*(?P<title>[^\n]*)$", re.MULTILINE
)
_SUMMARY_HEADER = re.compile(r"^##[ \t]*פגישה[ \t]*(?P<n>\d+)[ \t]*$", re.MULTILINE)
# The private clinical note, e.g. '🎙️ הקלטת המטפל (Note): "..."'.
_NOTE = re.compile(rf'^{NOTE_MARKER}[^"\n]*"(?P<text>.+?)"[ \t]*$', re.DOTALL | re.MULTILINE)
# The dictated recording: the first fully quoted block of the section.
_QUOTE = re.compile(r'^"(?P<text>.+?)"[ \t]*$', re.DOTALL | re.MULTILINE)
# 'מואנה · 23/06/26 · 17:00 · 50 דק׳'
_META = re.compile(
    r"^(?P<name>[^\n·]+?)[ \t]*·[ \t]*(?P<day>\d{2})/(?P<month>\d{2})/(?P<year>\d{2})[ \t]*·"
    r"[ \t]*(?P<hour>\d{2}):(?P<minute>\d{2})[ \t]*·[ \t]*(?P<duration>\d+)[ \t]*דק",
    re.MULTILINE,
)
_TRAILING_RULE = re.compile(r"\n---[ \t]*$")


class MockParseError(ValueError):
    """Raised when a mock Markdown file does not match the expected structure."""


@dataclass(frozen=True)
class RecordedSession:
    """One ``## מפגש N`` section of ``recorded_sessions.md``."""

    n: int
    title: str
    transcript: str
    note: str


@dataclass(frozen=True)
class SummarySection:
    """One ``## פגישה N`` section of ``session_summaries.md``."""

    n: int
    title: str
    start_at: datetime
    duration_minutes: int
    text: str

    @property
    def end_at(self) -> datetime:
        return self.start_at + timedelta(minutes=self.duration_minutes)


def _split_sections(text: str, header: re.Pattern[str]) -> list[tuple[re.Match[str], str]]:
    """Pair every header match with the body running up to the next header."""
    matches = list(header.finditer(text))
    return [
        (
            match,
            text[match.end() : (matches[i + 1].start() if i + 1 < len(matches) else len(text))],
        )
        for i, match in enumerate(matches)
    ]


def _clean(body: str) -> str:
    """Trim surrounding whitespace and the horizontal rule that ends a section."""
    return _TRAILING_RULE.sub("", body.strip()).strip()


def parse_recorded(text: str) -> dict[int, RecordedSession]:
    """Parse a ``recorded_sessions.md`` file, keyed by session number."""
    sections = _split_sections(text, _RECORDED_HEADER)
    if not sections:
        raise MockParseError("no '## מפגש N' sections found")

    parsed: dict[int, RecordedSession] = {}
    for match, raw_body in sections:
        n = int(match.group("n"))
        if n in parsed:
            raise MockParseError(f"session {n}: duplicate '## מפגש' section")
        body = _clean(raw_body)
        note_match = _NOTE.search(body)
        if note_match is None:
            raise MockParseError(f"session {n}: no '{NOTE_MARKER}' therapist note found")
        # Look for the recording only above the note, so a section that has no
        # recording cannot silently reuse the note's quoted text.
        quote_match = _QUOTE.search(body[: note_match.start()])
        if quote_match is None:
            raise MockParseError(f"session {n}: no quoted recording found")
        parsed[n] = RecordedSession(
            n=n,
            title=match.group("title").strip(),
            transcript=quote_match.group("text").strip(),
            note=note_match.group("text").strip(),
        )
    return parsed


def parse_summaries(text: str) -> tuple[str, dict[int, SummarySection]]:
    """Parse a ``session_summaries.md`` file into the patient name and sections."""
    sections = _split_sections(text, _SUMMARY_HEADER)
    if not sections:
        raise MockParseError("no '## פגישה N' sections found")

    names: set[str] = set()
    parsed: dict[int, SummarySection] = {}
    for match, raw_body in sections:
        n = int(match.group("n"))
        if n in parsed:
            raise MockParseError(f"session {n}: duplicate '## פגישה' section")
        block = _clean(raw_body)
        meta = _META.search(block)
        if meta is None:
            raise MockParseError(f"session {n}: no '<name> · DD/MM/YY · HH:MM · N דק׳' line found")
        title = block.split("\n", 1)[0].strip()
        if not title:
            raise MockParseError(f"session {n}: summary block has no title line")
        names.add(meta.group("name").strip())
        parsed[n] = SummarySection(
            n=n,
            title=title,
            start_at=datetime(
                2000 + int(meta.group("year")),
                int(meta.group("month")),
                int(meta.group("day")),
                int(meta.group("hour")),
                int(meta.group("minute")),
                tzinfo=ISRAEL_TZ,
            ),
            duration_minutes=int(meta.group("duration")),
            text=block,
        )
    if len(names) != 1:
        raise MockParseError(f"expected one patient name, found {sorted(names)}")
    return names.pop(), parsed
