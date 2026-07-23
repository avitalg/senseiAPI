# Mock-patient seed regeneration — implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Regenerate `seeds/patients/*.json` from `../sensei-patients/mock_patients` so the demo database carries all 11 mock patients with real structured session summaries.

**Architecture:** A pure Markdown parser (`seeds/mock_parser.py`) plus a development-time CLI (`seeds/generate.py`) that writes the committed JSON corpus. `seeds/load.py` gains one change — composing `transcripts.raw_text` from the new `note` key — and is otherwise untouched. The API never reads the external mock repo.

**Tech Stack:** Python 3.11, `re`, `dataclasses`, `zoneinfo`, `argparse`, pytest.

**Spec:** `docs/superpowers/specs/2026-07-23-mock-patients-seed-design.md`

## Global Constraints

- Full type hints on every function; `mypy` runs in `strict` mode (`pyproject.toml`).
- `ruff` line-length 100, rules `E,F,I,UP,B,SIM`.
- Use `logging`, never `print`.
- Catch the narrowest exception; never `except: pass`.
- Every behaviour change ships with pytest tests under `tests/test_*.py`.
- Tests must be deterministic and hit no network, no live database, and no path outside `tmp_path` — never the real `../sensei-patients` checkout.
- Seed user id is `3fa85f64-5717-4562-b3fc-2c963f66afa6`.
- Sessions per patient: 5, numbered 1–5.
- `calendar_events.title` is `String(255)` — titles must fit.
- Timestamps carry the `Asia/Jerusalem` offset (`+03:00` for every mock date).
- Before declaring the work done, all four must pass: `ruff check .`, `ruff format --check .`, `mypy .`, `pytest`.

## File Structure

| File | Responsibility |
|---|---|
| `seeds/mock_parser.py` | **create** — pure text→dataclass parsing of the two Markdown formats. No IO. |
| `seeds/generate.py` | **create** — CLI: walk the mock dir, join the two halves, attach contacts, validate, write JSON. |
| `seeds/load.py` | **modify** — compose `raw_text` from `transcript` + optional `note`. |
| `seeds/patients/*.json` | **replace** — delete the 9 old files, commit 11 generated ones. |
| `tests/test_mock_parser.py` | **create** — parser units against inline fixture Markdown. |
| `tests/test_seed_generate.py` | **create** — generator units against a `tmp_path` mock directory. |
| `tests/test_seed_load.py` | **create** — `raw_text` composition. |
| `tests/test_seed_files.py` | **create** — validate the committed corpus. |
| `docs/seeds/mock-patient-seed-regeneration-23-07-2026-report.md` | **create** — what changed and how to regenerate. |

---

### Task 1: Markdown parser

**Files:**
- Create: `seeds/mock_parser.py`
- Test: `tests/test_mock_parser.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `MockParseError(ValueError)`
  - `ISRAEL_TZ: ZoneInfo`
  - `NOTE_MARKER: str` (`"🎙️"`)
  - `RecordedSession(n: int, title: str, transcript: str, note: str)` — frozen dataclass
  - `SummarySection(n: int, title: str, start_at: datetime, duration_minutes: int, text: str)` — frozen dataclass with property `end_at: datetime`
  - `parse_recorded(text: str) -> dict[int, RecordedSession]`
  - `parse_summaries(text: str) -> tuple[str, dict[int, SummarySection]]`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_mock_parser.py`:

```python
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from seeds.mock_parser import MockParseError, parse_recorded, parse_summaries

RECORDED = """\
# מואנה — תיק מטופלת (Mock Data)

**גישה טיפולית מרכזית:** טיפול נרטיבי

---

## מפגש 1: היכרות ומיפוי

"תמליל ראשון."

🎙️ הקלטת המטפל (Note): "הערה ראשונה."

---

## מפגש 2: חיצון הבעיה

"תמליל שני."

🎙️ הקלטת המטפל (Note): "הערה שנייה."
"""

# simba's file carries no per-session titles — the header is a bare "## מפגש N".
UNTITLED_RECORDED = """\
# סימבה — תיק מטופל (Mock Data)

---

## מפגש 1

"תמליל ראשון."

🎙️ הקלטת המטפל (Note): "הערה ראשונה."
"""

SUMMARIES = """\
# מואנה — סיכומי מפגשים (פלט מערכת)

---

## פגישה 1
מיפוי הסיפור השולט

מואנה · 23/06/26 · 17:00 · 50 דק׳

**תובנות מרכזיות**
תובנה ראשונה.

---

## פגישה 2
חיצון הבעיה

מואנה · 30/06/26 · 17:00 · 40 דק׳

**תובנות מרכזיות**
תובנה שנייה.
"""


def test_parse_recorded_extracts_title_transcript_and_note() -> None:
    sessions = parse_recorded(RECORDED)

    assert sorted(sessions) == [1, 2]
    assert sessions[1].title == "היכרות ומיפוי"
    assert sessions[1].transcript == "תמליל ראשון."
    assert sessions[1].note == "הערה ראשונה."
    assert sessions[2].title == "חיצון הבעיה"
    assert sessions[2].transcript == "תמליל שני."


def test_parse_recorded_keeps_note_out_of_transcript() -> None:
    sessions = parse_recorded(RECORDED)

    assert "הערה ראשונה" not in sessions[1].transcript
    assert "🎙️" not in sessions[1].transcript


def test_parse_recorded_handles_untitled_header() -> None:
    sessions = parse_recorded(UNTITLED_RECORDED)

    assert sessions[1].title == ""
    assert sessions[1].transcript == "תמליל ראשון."
    assert sessions[1].note == "הערה ראשונה."


def test_parse_recorded_raises_without_sections() -> None:
    with pytest.raises(MockParseError, match="מפגש"):
        parse_recorded("# כותרת בלבד\n")


def test_parse_recorded_raises_when_note_missing() -> None:
    text = '## מפגש 1: כותרת\n\n"תמליל ללא הערה."\n'

    with pytest.raises(MockParseError, match="note"):
        parse_recorded(text)


def test_parse_recorded_raises_when_recording_missing() -> None:
    text = '## מפגש 1: כותרת\n\n🎙️ הקלטת המטפל (Note): "הערה בלבד."\n'

    with pytest.raises(MockParseError, match="recording"):
        parse_recorded(text)


def test_parse_recorded_raises_on_duplicate_session() -> None:
    text = (
        '## מפגש 1: א\n\n"תמליל."\n\n🎙️ הקלטת המטפל (Note): "הערה."\n\n'
        '## מפגש 1: ב\n\n"תמליל."\n\n🎙️ הקלטת המטפל (Note): "הערה."\n'
    )

    with pytest.raises(MockParseError, match="duplicate"):
        parse_recorded(text)


def test_parse_summaries_returns_name_and_sections() -> None:
    name, sections = parse_summaries(SUMMARIES)

    assert name == "מואנה"
    assert sorted(sections) == [1, 2]
    assert sections[1].title == "מיפוי הסיפור השולט"
    assert sections[1].text.startswith("מיפוי הסיפור השולט")
    assert "תובנה ראשונה." in sections[1].text
    assert "תובנה שנייה." not in sections[1].text


def test_parse_summaries_uses_israel_time() -> None:
    _, sections = parse_summaries(SUMMARIES)

    assert sections[1].start_at == datetime(
        2026, 6, 23, 17, 0, tzinfo=ZoneInfo("Asia/Jerusalem")
    )
    assert sections[1].start_at.utcoffset() is not None
    assert sections[1].start_at.strftime("%z") == "+0300"


def test_parse_summaries_end_at_adds_duration() -> None:
    _, sections = parse_summaries(SUMMARIES)

    assert sections[1].duration_minutes == 50
    assert sections[1].end_at == datetime(
        2026, 6, 23, 17, 50, tzinfo=ZoneInfo("Asia/Jerusalem")
    )
    assert sections[2].duration_minutes == 40
    assert sections[2].end_at == datetime(
        2026, 6, 30, 17, 40, tzinfo=ZoneInfo("Asia/Jerusalem")
    )


def test_parse_summaries_strips_trailing_rule() -> None:
    _, sections = parse_summaries(SUMMARIES)

    assert not sections[1].text.endswith("---")


def test_parse_summaries_raises_without_meta_line() -> None:
    text = "## פגישה 1\nכותרת\n\n**תובנות מרכזיות**\nתובנה.\n"

    with pytest.raises(MockParseError, match="דק"):
        parse_summaries(text)


def test_parse_summaries_raises_without_sections() -> None:
    with pytest.raises(MockParseError, match="פגישה"):
        parse_summaries("# כותרת בלבד\n")


def test_parse_summaries_raises_on_conflicting_names() -> None:
    text = (
        "## פגישה 1\nכותרת\n\nמואנה · 23/06/26 · 17:00 · 50 דק׳\n\nגוף.\n\n"
        "## פגישה 2\nכותרת\n\nסימבה · 30/06/26 · 17:00 · 50 דק׳\n\nגוף.\n"
    )

    with pytest.raises(MockParseError, match="one patient name"):
        parse_summaries(text)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_mock_parser.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'seeds.mock_parser'`

- [ ] **Step 3: Write the parser**

Create `seeds/mock_parser.py`:

```python
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
            raise MockParseError(
                f"session {n}: no '<name> · DD/MM/YY · HH:MM · N דק׳' line found"
            )
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
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_mock_parser.py -q`
Expected: PASS, 13 tests.

- [ ] **Step 5: Verify the parser against the real corpus**

Run:

```bash
.venv/bin/python -c "
from pathlib import Path
from seeds.mock_parser import parse_recorded, parse_summaries
root = Path('../sensei-patients/mock_patients')
for d in sorted(p for p in root.iterdir() if p.is_dir()):
    rec = parse_recorded((d / 'recorded_sessions.md').read_text(encoding='utf-8'))
    name, sums = parse_summaries((d / 'session_summaries.md').read_text(encoding='utf-8'))
    assert sorted(rec) == sorted(sums) == [1, 2, 3, 4, 5], d.name
    print(f'{d.name:14} {name}')
"
```

Expected: 11 lines, no assertion error, names `אלאדין ברוס וויין דמבו אלזה פורסט גאמפ הארי פוטר מרלין מואנה מולאן רפונזל סימבה`.

- [ ] **Step 6: Lint, format and typecheck**

Run: `.venv/bin/ruff check seeds tests && .venv/bin/ruff format seeds tests && .venv/bin/python -m mypy seeds tests`
Expected: all clean.

- [ ] **Step 7: Commit**

```bash
git add seeds/mock_parser.py tests/test_mock_parser.py
git commit -m "feat(seeds): parse the mock-patient markdown corpus"
```

---

### Task 2: Seed generator CLI

**Files:**
- Create: `seeds/generate.py`
- Test: `tests/test_seed_generate.py`

**Interfaces:**
- Consumes: `seeds.mock_parser.{MockParseError, RecordedSession, SummarySection, parse_recorded, parse_summaries}`
- Produces:
  - `Contact(phone: str, email: str | None = None)` — frozen dataclass
  - `CONTACTS: dict[str, Contact]`
  - `SEED_USER_ID: str`, `SESSIONS_PER_PATIENT: int`, `TITLE_MAX_LENGTH: int`
  - `DEFAULT_SOURCE: Path`, `OUTPUT_DIR: Path`
  - `build_patient(slug: str, recorded_text: str, summaries_text: str) -> dict[str, Any]`
  - `generate(source: Path, output_dir: Path) -> list[str]`
  - `main() -> None`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_seed_generate.py`:

```python
import json
from pathlib import Path

import pytest

from seeds.generate import CONTACTS, SEED_USER_ID, build_patient, generate
from seeds.mock_parser import MockParseError

RECORDED = "".join(
    f'## מפגש {n}: כותרת {n}\n\n"תמליל {n}."\n\n'
    f'🎙️ הקלטת המטפל (Note): "הערה {n}."\n\n---\n\n'
    for n in range(1, 6)
)

UNTITLED_RECORDED = "".join(
    f'## מפגש {n}\n\n"תמליל {n}."\n\n'
    f'🎙️ הקלטת המטפל (Note): "הערה {n}."\n\n---\n\n'
    for n in range(1, 6)
)

SUMMARIES = "".join(
    f"## פגישה {n}\nסיכום כותרת {n}\n\n"
    f"מואנה · 2{n}/06/26 · 17:00 · 50 דק׳\n\n"
    f"**תובנות מרכזיות**\nתובנה {n}.\n\n---\n\n"
    for n in range(1, 6)
)


def _write_mock(root: Path, slug: str, recorded: str = RECORDED) -> Path:
    directory = root / slug
    directory.mkdir(parents=True)
    (directory / "recorded_sessions.md").write_text(recorded, encoding="utf-8")
    (directory / "session_summaries.md").write_text(SUMMARIES, encoding="utf-8")
    return directory


def test_build_patient_returns_seed_payload() -> None:
    payload = build_patient("moana", RECORDED, SUMMARIES)

    assert payload["slug"] == "moana"
    assert payload["user_id"] == SEED_USER_ID
    assert payload["name"] == "מואנה"
    assert payload["phone"] == CONTACTS["moana"].phone
    assert payload["email"] == CONTACTS["moana"].email
    assert [s["n"] for s in payload["sessions"]] == [1, 2, 3, 4, 5]


def test_build_patient_maps_session_fields() -> None:
    session = build_patient("moana", RECORDED, SUMMARIES)["sessions"][0]

    assert session["title"] == "מפגש 1: כותרת 1"
    assert session["transcript"] == "תמליל 1."
    assert session["note"] == "הערה 1."
    assert session["summary"].startswith("סיכום כותרת 1")
    assert session["start_at"] == "2026-06-21T17:00:00+03:00"
    assert session["end_at"] == "2026-06-21T17:50:00+03:00"


def test_build_patient_falls_back_to_summary_title() -> None:
    session = build_patient("moana", UNTITLED_RECORDED, SUMMARIES)["sessions"][0]

    assert session["title"] == "מפגש 1: סיכום כותרת 1"


def test_build_patient_rejects_unknown_slug() -> None:
    with pytest.raises(MockParseError, match="CONTACTS"):
        build_patient("nobody", RECORDED, SUMMARIES)


def test_build_patient_rejects_wrong_session_count() -> None:
    short = '## מפגש 1: כותרת\n\n"תמליל."\n\n🎙️ הקלטת המטפל (Note): "הערה."\n'

    with pytest.raises(MockParseError, match="expected sessions"):
        build_patient("moana", short, SUMMARIES)


def test_build_patient_rejects_overlong_title() -> None:
    long_title = "כ" * 300
    recorded = "".join(
        f'## מפגש {n}: {long_title}\n\n"תמליל {n}."\n\n'
        f'🎙️ הקלטת המטפל (Note): "הערה {n}."\n\n---\n\n'
        for n in range(1, 6)
    )

    with pytest.raises(MockParseError, match="max 255"):
        build_patient("moana", recorded, SUMMARIES)


def test_generate_writes_one_file_per_patient(tmp_path: Path) -> None:
    source = tmp_path / "mock_patients"
    _write_mock(source, "moana")
    _write_mock(source, "simba", recorded=UNTITLED_RECORDED)
    output = tmp_path / "patients"

    written = generate(source, output)

    assert written == ["moana", "simba"]
    payload = json.loads((output / "moana.json").read_text(encoding="utf-8"))
    assert payload["slug"] == "moana"
    assert len(payload["sessions"]) == 5


def test_generate_writes_readable_unicode(tmp_path: Path) -> None:
    source = tmp_path / "mock_patients"
    _write_mock(source, "moana")
    output = tmp_path / "patients"

    generate(source, output)

    raw = (output / "moana.json").read_text(encoding="utf-8")
    assert "מואנה" in raw
    assert raw.endswith("\n")


def test_generate_rejects_empty_source(tmp_path: Path) -> None:
    source = tmp_path / "mock_patients"
    source.mkdir()

    with pytest.raises(SystemExit, match="No mock patient directories"):
        generate(source, tmp_path / "patients")
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_seed_generate.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'seeds.generate'`

- [ ] **Step 3: Write the generator**

Create `seeds/generate.py`:

```python
"""Regenerate ``seeds/patients/*.json`` from the sensei-patients mock corpus.

Development-time tool — the running API never invokes it. Point it at a checkout
of the mock-data repo and it rewrites the committed seed corpus::

    .venv/bin/python -m seeds.generate --source ../sensei-patients/mock_patients

The mock Markdown carries no contact details, so they live in ``CONTACTS`` below:
the four patients that predate this corpus keep the phone and email their old
seed file carried, and the rest get synthetic values.
"""

from __future__ import annotations

import argparse
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from seeds.mock_parser import (
    MockParseError,
    RecordedSession,
    SummarySection,
    parse_recorded,
    parse_summaries,
)

logger = logging.getLogger(__name__)

# ../sensei-patients sits next to this repository in the same parent directory.
DEFAULT_SOURCE = Path(__file__).resolve().parents[2] / "sensei-patients" / "mock_patients"
OUTPUT_DIR = Path(__file__).with_name("patients")

SEED_USER_ID = "3fa85f64-5717-4562-b3fc-2c963f66afa6"
SESSIONS_PER_PATIENT = 5
TITLE_MAX_LENGTH = 255  # calendar_events.title is String(255)


@dataclass(frozen=True)
class Contact:
    """Contact details for a seeded patient; ``patients.phone`` is not nullable."""

    phone: str
    email: str | None = None


CONTACTS: dict[str, Contact] = {
    "aladdin": Contact("+972-52-4001122", "aladdin@example.com"),
    "bruce_wayne": Contact("+972-54-4002233", "bruce.wayne@example.com"),
    "dumbo": Contact("+972-53-4003344", "dumbo@example.com"),
    "elsa": Contact("+972-52-8877665", "elsa@example.com"),
    "forrest_gump": Contact("+972-50-7654321"),
    "harry_potter": Contact("+972-50-9998887"),
    "marlin": Contact("+972-50-4004455", "marlin@example.com"),
    "moana": Contact("+972-52-4005566", "moana@example.com"),
    "mulan": Contact("+972-54-4006677", "mulan@example.com"),
    "rapunzel": Contact("+972-53-4007788", "rapunzel@example.com"),
    "simba": Contact("+972-50-1234567"),
}


def _session(slug: str, recorded: RecordedSession, summary: SummarySection) -> dict[str, Any]:
    """Join one session's two halves into its seed JSON object."""
    title = f"מפגש {recorded.n}: {recorded.title or summary.title}"
    if len(title) > TITLE_MAX_LENGTH:
        raise MockParseError(
            f"{slug} session {recorded.n}: title is {len(title)} chars (max {TITLE_MAX_LENGTH})"
        )
    if summary.duration_minutes <= 0:
        raise MockParseError(f"{slug} session {recorded.n}: duration must be positive")
    return {
        "n": recorded.n,
        "title": title,
        "start_at": summary.start_at.isoformat(),
        "end_at": summary.end_at.isoformat(),
        "transcript": recorded.transcript,
        "note": recorded.note,
        "summary": summary.text,
    }


def build_patient(slug: str, recorded_text: str, summaries_text: str) -> dict[str, Any]:
    """Turn one patient's two Markdown files into their seed JSON payload."""
    contact = CONTACTS.get(slug)
    if contact is None:
        raise MockParseError(f"{slug}: unknown patient — add an entry to CONTACTS")

    recorded = parse_recorded(recorded_text)
    name, summaries = parse_summaries(summaries_text)
    expected = list(range(1, SESSIONS_PER_PATIENT + 1))
    if sorted(recorded) != expected or sorted(summaries) != expected:
        raise MockParseError(
            f"{slug}: expected sessions {expected}, got "
            f"recorded={sorted(recorded)} summaries={sorted(summaries)}"
        )

    return {
        "user_id": SEED_USER_ID,
        "slug": slug,
        "name": name,
        "phone": contact.phone,
        "email": contact.email,
        "sessions": [_session(slug, recorded[n], summaries[n]) for n in expected],
    }


def generate(source: Path, output_dir: Path) -> list[str]:
    """Write one seed JSON file per mock patient directory; returns the slugs written."""
    directories = sorted(path for path in source.iterdir() if path.is_dir())
    if not directories:
        raise SystemExit(f"No mock patient directories found in {source}")

    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    for directory in directories:
        slug = directory.name
        payload = build_patient(
            slug,
            (directory / "recorded_sessions.md").read_text(encoding="utf-8"),
            (directory / "session_summaries.md").read_text(encoding="utf-8"),
        )
        destination = output_dir / f"{slug}.json"
        destination.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        logger.info("Wrote %s.", destination.name)
        written.append(slug)
    return written


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Regenerate the patient seed corpus.")
    parser.add_argument(
        "--source",
        type=Path,
        default=DEFAULT_SOURCE,
        help=f"mock_patients directory (default: {DEFAULT_SOURCE})",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=OUTPUT_DIR,
        help=f"seed output directory (default: {OUTPUT_DIR})",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    slugs = generate(args.source, args.output)
    logger.info("Done — %d patients written.", len(slugs))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_seed_generate.py -q`
Expected: PASS, 9 tests.

- [ ] **Step 5: Lint, format and typecheck**

Run: `.venv/bin/ruff check seeds tests && .venv/bin/ruff format seeds tests && .venv/bin/python -m mypy seeds tests`
Expected: all clean.

- [ ] **Step 6: Commit**

```bash
git add seeds/generate.py tests/test_seed_generate.py
git commit -m "feat(seeds): add mock-patient seed generator CLI"
```

---

### Task 3: Loader composes the transcript from recording + note

**Files:**
- Modify: `seeds/load.py:87-97`
- Test: `tests/test_seed_load.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: `seeds.load.NOTE_PREFIX: str`, `seeds.load._raw_text(session: dict[str, Any]) -> str`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_seed_load.py`:

```python
from typing import Any

from seeds.load import NOTE_PREFIX, _raw_text


def test_raw_text_appends_the_therapist_note() -> None:
    session: dict[str, Any] = {"transcript": "תמליל.", "note": "הערה."}

    assert _raw_text(session) == f"תמליל.\n\n{NOTE_PREFIX}הערה."


def test_raw_text_without_note_returns_the_transcript() -> None:
    session: dict[str, Any] = {"transcript": "תמליל."}

    assert _raw_text(session) == "תמליל."


def test_raw_text_ignores_an_empty_note() -> None:
    session: dict[str, Any] = {"transcript": "תמליל.", "note": ""}

    assert _raw_text(session) == "תמליל."


def test_note_prefix_keeps_the_source_marker() -> None:
    assert NOTE_PREFIX.startswith("🎙️")
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_seed_load.py -q`
Expected: FAIL — `ImportError: cannot import name 'NOTE_PREFIX' from 'seeds.load'`

- [ ] **Step 3: Add the composition helper**

In `seeds/load.py`, add below the `SEED_NAMESPACE` definition:

```python
# Prefix mirroring the marker the mock corpus uses for the therapist's private note.
NOTE_PREFIX = "🎙️ הקלטת המטפל (Note): "
```

and add this function below `_sid`:

```python
def _raw_text(session: dict[str, Any]) -> str:
    """Compose a transcript: the dictated recording plus the therapist's private note.

    Seed files written before the note existed simply omit the key, so they keep
    loading unchanged.
    """
    transcript = str(session["transcript"])
    note = session.get("note")
    if not note:
        return transcript
    return f"{transcript}\n\n{NOTE_PREFIX}{note}"
```

- [ ] **Step 4: Use it in the loader**

In `seeds/load.py`, inside `_seed_patient`, change the `TranscriptRecord` merge from:

```python
                raw_text=s["transcript"],
```

to:

```python
                raw_text=_raw_text(s),
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_seed_load.py -q`
Expected: PASS, 4 tests.

- [ ] **Step 6: Lint, format and typecheck**

Run: `.venv/bin/ruff check seeds tests && .venv/bin/ruff format seeds tests && .venv/bin/python -m mypy seeds tests`
Expected: all clean.

- [ ] **Step 7: Commit**

```bash
git add seeds/load.py tests/test_seed_load.py
git commit -m "feat(seeds): append the therapist note to seeded transcripts"
```

---

### Task 4: Regenerate the corpus

**Files:**
- Delete: `seeds/patients/{eeyore,elsa,forrest,gollum,harry,hermione,shrek,simba,woody}.json`
- Create: `seeds/patients/{aladdin,bruce_wayne,dumbo,elsa,forrest_gump,harry_potter,marlin,moana,mulan,rapunzel,simba}.json`
- Test: `tests/test_seed_files.py`

**Interfaces:**
- Consumes: `seeds.generate.{CONTACTS, SEED_USER_ID, SESSIONS_PER_PATIENT, TITLE_MAX_LENGTH, OUTPUT_DIR}`
- Produces: the committed seed corpus.

- [ ] **Step 1: Write the failing corpus test**

Create `tests/test_seed_files.py`:

```python
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest

from seeds.generate import CONTACTS, OUTPUT_DIR, SEED_USER_ID, SESSIONS_PER_PATIENT, TITLE_MAX_LENGTH

EXPECTED_SLUGS = {
    "aladdin",
    "bruce_wayne",
    "dumbo",
    "elsa",
    "forrest_gump",
    "harry_potter",
    "marlin",
    "moana",
    "mulan",
    "rapunzel",
    "simba",
}


def _seed_files() -> list[Path]:
    return sorted(OUTPUT_DIR.glob("*.json"))


def _load(path: Path) -> dict[str, Any]:
    payload: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return payload


def test_corpus_holds_exactly_the_expected_patients() -> None:
    assert {path.stem for path in _seed_files()} == EXPECTED_SLUGS


def test_contacts_cover_every_seed_file() -> None:
    assert EXPECTED_SLUGS <= set(CONTACTS)


@pytest.mark.parametrize("path", _seed_files(), ids=lambda path: path.stem)
def test_seed_file_is_well_formed(path: Path) -> None:
    payload = _load(path)

    assert payload["slug"] == path.stem
    assert payload["user_id"] == SEED_USER_ID
    assert payload["name"].strip()
    assert payload["phone"] == CONTACTS[path.stem].phone
    assert payload["email"] == CONTACTS[path.stem].email

    sessions = payload["sessions"]
    assert [s["n"] for s in sessions] == list(range(1, SESSIONS_PER_PATIENT + 1))

    for session in sessions:
        start_at = datetime.fromisoformat(session["start_at"])
        end_at = datetime.fromisoformat(session["end_at"])
        assert end_at > start_at
        assert start_at.strftime("%z") == "+0300"
        assert 0 < len(session["title"]) <= TITLE_MAX_LENGTH
        assert session["transcript"].strip()
        assert session["note"].strip()
        assert session["summary"].strip()
        assert "🎙️" not in session["transcript"]


def test_no_two_patients_share_a_start_time() -> None:
    starts = [
        session["start_at"] for path in _seed_files() for session in _load(path)["sessions"]
    ]

    assert len(starts) == len(set(starts))
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_seed_files.py -q`
Expected: FAIL — the slug set is the old nine, not `EXPECTED_SLUGS`.

- [ ] **Step 3: Delete the old corpus**

```bash
git rm seeds/patients/eeyore.json seeds/patients/elsa.json seeds/patients/forrest.json \
       seeds/patients/gollum.json seeds/patients/harry.json seeds/patients/hermione.json \
       seeds/patients/shrek.json seeds/patients/simba.json seeds/patients/woody.json
```

- [ ] **Step 4: Generate the new corpus**

Run: `.venv/bin/python -m seeds.generate --source ../sensei-patients/mock_patients`
Expected: 11 `Wrote <slug>.json.` lines, then `Done — 11 patients written.`

- [ ] **Step 5: Run the test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_seed_files.py -q`
Expected: PASS, 14 tests.

- [ ] **Step 6: Spot-check the generated content**

Run:

```bash
.venv/bin/python -c "
import json
from pathlib import Path
d = json.loads(Path('seeds/patients/simba.json').read_text(encoding='utf-8'))
s = d['sessions'][0]
print(d['name'], d['phone'], d['email'])
print(s['title'])
print(s['start_at'], '->', s['end_at'])
print('transcript:', s['transcript'][:60])
print('note:', s['note'][:60])
print('summary head:', s['summary'].split(chr(10))[0])
"
```

Expected: `סימבה +972-50-1234567 None`; title `מפגש 1: יצירת קשר ראשוני וזיהוי דפוס הימנעות נוקשה` (the fallback from `session_summaries.md`, since simba's recorded headers carry no title); `2026-06-21T10:00:00+03:00 -> 2026-06-21T10:50:00+03:00`.

- [ ] **Step 7: Commit**

```bash
git add seeds/patients tests/test_seed_files.py
git commit -m "feat(seeds): regenerate the patient corpus from mock_patients"
```

---

### Task 5: Verification and documentation

**Files:**
- Create: `docs/seeds/mock-patient-seed-regeneration-23-07-2026-report.md`

**Interfaces:**
- Consumes: everything above.
- Produces: nothing consumed by later tasks.

- [ ] **Step 1: Run the full gate**

Run: `.venv/bin/ruff check . && .venv/bin/ruff format --check . && .venv/bin/python -m mypy . && .venv/bin/python -m pytest -q`
Expected: all four pass. Fix anything that fails before continuing.

- [ ] **Step 2: Verify the corpus loads into a database**

Only if a local Postgres is available (see `LOCAL_DEPLOY.md`); otherwise record that this step was skipped.

```bash
docker compose up -d db
DATABASE_URL=<local url> .venv/bin/python -m seeds.load
```

Expected: 11 `Seeded <name> (<slug>) with 5 sessions.` lines, then `Done — 11 patients seeded.`

- [ ] **Step 3: Write the report**

Create `docs/seeds/mock-patient-seed-regeneration-23-07-2026-report.md`:

```markdown
# Patient seed regeneration from mock_patients (23-07-2026)

The seed corpus is now generated from `../sensei-patients/mock_patients` instead
of being written by hand. Eleven patients, five sessions each.

## Regenerating

    .venv/bin/python -m seeds.generate --source ../sensei-patients/mock_patients

Then commit the changed `seeds/patients/*.json`. `seeds/load.py` is unchanged by
a regeneration — it still reads the committed JSON at runtime, so the API never
depends on the mock repo.

New patient in the mock repo? Add a `CONTACTS` entry in `seeds/generate.py` and
add the slug to `EXPECTED_SLUGS` in `tests/test_seed_files.py` — the generator
refuses to write a patient it has no contact details for.

## What changed

- **Roster:** `eeyore`, `gollum`, `hermione`, `shrek` and `woody` are gone — they
  have no mock source. `harry` → `harry_potter`, `forrest` → `forrest_gump`.
  Added `aladdin`, `bruce_wayne`, `dumbo`, `marlin`, `moana`, `mulan`, `rapunzel`.
  `elsa` is a different patient now: the mock file is CFT / self-criticism, the
  old seed was panic + interoceptive exposure.
- **Summaries are real.** `meeting_summaries.text` now holds the structured block
  from `session_summaries.md` verbatim. Previously it held the therapist's
  dictated recording.
- **Transcripts are the recording.** `transcripts.raw_text` is the dictated
  recording followed by the private `🎙️` note. Previously it held only the note.
- **Timestamps carry `+03:00`.** `assistant/context.py` renders stored timestamps
  in Israel time, so the assistant now reports the same time that is printed
  inside the summary text. The old seeds stored `+00:00` and read three hours off.

## Stale rows

`seeds/load.py` upserts and never deletes. A database seeded with the old corpus
keeps the five removed patients plus orphaned `harry` and `forrest` rows. This is
accepted for demo data — pruning would have to delete by `user_id`, which would
also remove real patients created under the demo therapist. Drop the database to
get a clean roster.
```

- [ ] **Step 4: Commit**

```bash
git add docs/seeds docs/superpowers
git commit -m "docs(seeds): record the mock-patient regeneration"
```

---

## Self-Review

**Spec coverage:**

| Spec item | Task |
|---|---|
| Parser handles simba's untitled headers | 1 (test + fallback in 2) |
| Parser takes the name from the metadata line | 1 |
| `MockParseError` on malformed input | 1, 2 |
| Generator CLI, contact table, validation | 2 |
| Title ≤ 255, `end_at > start_at`, 5 sessions | 2 (build) + 4 (corpus) |
| `Asia/Jerusalem` timestamps | 1 (parse) + 4 (corpus assertion) |
| Summary stored verbatim | 1 (`text=block`) + 2 |
| `raw_text` = recording + note | 3 |
| Seed JSON gains `note`, loader backward-compatible | 3 |
| Delete the five sourceless patients, rename two slugs | 4 |
| Stale rows accepted, no pruning code | 5 (report only) |
| No network / no live DB in tests | 1–4 |

**Placeholders:** none — every step carries its command or its code.

**Type consistency:** `parse_recorded`/`parse_summaries` signatures in Task 1 match their use in Task 2; `RecordedSession.title`/`SummarySection.title` back the fallback in `_session`; `NOTE_PREFIX` and `_raw_text` in Task 3 match their import in `tests/test_seed_load.py`; `CONTACTS`, `SEED_USER_ID`, `SESSIONS_PER_PATIENT`, `TITLE_MAX_LENGTH` and `OUTPUT_DIR` in Task 2 match their import in Task 4.
