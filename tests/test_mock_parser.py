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

    assert sections[1].start_at == datetime(2026, 6, 23, 17, 0, tzinfo=ZoneInfo("Asia/Jerusalem"))
    assert sections[1].start_at.strftime("%z") == "+0300"


def test_parse_summaries_end_at_adds_duration() -> None:
    _, sections = parse_summaries(SUMMARIES)

    assert sections[1].duration_minutes == 50
    assert sections[1].end_at == datetime(2026, 6, 23, 17, 50, tzinfo=ZoneInfo("Asia/Jerusalem"))
    assert sections[2].duration_minutes == 40
    assert sections[2].end_at == datetime(2026, 6, 30, 17, 40, tzinfo=ZoneInfo("Asia/Jerusalem"))


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
