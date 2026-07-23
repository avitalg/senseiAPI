import json

import pytest

from seeds.generate import OUTPUT_DIR
from summaries.structure import parse_summary_sections

SEEDED_SUMMARY = """\
מיפוי נקודות תקיעה — פציעה מוסרית

מולאן · 24/06/26 · 15:00 · 50 דק׳

**תובנות מרכזיות**
זוהה שילוב של אשמה על ההטעיה עצמה ואשמה מעוותת על תוצאות קרב שלא היו בשליטתה.

**סיכום הפגישה**

מטופלת דיברה בקור רוח על קרבות ואובדן חברים, אך השתנתה כליל כשעלה נושא ההתחזות.

**נושאים מרכזיים**
- פציעה מוסרית (moral injury)
- אשמה על הטעיה מול אשמה על תוצאות קרב
- קושי בחשיפה רגשית

**דגלי סיכון**
*(אינדיקטור בלבד. אינו מהווה אבחנה רפואית)*
**בינוני** — אשמה עמוקה ומורכבת, נדרשת עבודה הדרגתית ומובנית."""

LIVE_SUMMARY = """\
## תובנות מרכזיות
החרדה מתעוררת סביב אירועי עבודה.

## נושאים מרכזיים
- חרדה בעבודה
- דפוסי שינה

## התערבויות המטפל/ת
- שיקוף החרדה
- תרגול נשימה

## סימני סיכון
לא נאמרו אמירות מפורשות של סיכון

## המשך ומעקב
- מעקב שינה"""


def test_parses_the_seeded_bold_heading_format() -> None:
    parsed = parse_summary_sections(SEEDED_SUMMARY)

    assert parsed is not None
    assert parsed.title == "מיפוי נקודות תקיעה — פציעה מוסרית"
    assert parsed.subtitle == "מולאן · 24/06/26 · 15:00 · 50 דק׳"
    assert parsed.insights is not None
    assert parsed.insights.startswith("זוהה שילוב של אשמה")
    assert parsed.session_summary is not None
    assert parsed.session_summary.startswith("מטופלת דיברה בקור רוח")
    assert parsed.session_main_topics == [
        "פציעה מוסרית (moral injury)",
        "אשמה על הטעיה מול אשמה על תוצאות קרב",
        "קושי בחשיפה רגשית",
    ]
    assert parsed.session_risk_flags is not None
    assert parsed.session_risk_flags.level == "בינוני"
    assert parsed.session_risk_flags.note == ("אשמה עמוקה ומורכבת, נדרשת עבודה הדרגתית ומובנית.")
    assert parsed.session_risk_flags.disclaimer == "אינדיקטור בלבד. אינו מהווה אבחנה רפואית"
    assert parsed.session_risk_flags.attention is None


def test_parses_the_live_atx_heading_format() -> None:
    parsed = parse_summary_sections(LIVE_SUMMARY)

    assert parsed is not None
    # Live output has no title lines above the first heading.
    assert parsed.title is None
    assert parsed.subtitle is None
    assert parsed.insights == "החרדה מתעוררת סביב אירועי עבודה."
    assert parsed.session_main_topics == ["חרדה בעבודה", "דפוסי שינה"]
    assert parsed.therapist_interventions == ["שיקוף החרדה", "תרגול נשימה"]
    assert parsed.follow_up == ["מעקב שינה"]
    assert parsed.session_summary is None
    assert parsed.session_risk_flags is not None
    # No bold severity word in the live dialect — the whole line is the note.
    assert parsed.session_risk_flags.level is None
    assert parsed.session_risk_flags.note == "לא נאמרו אמירות מפורשות של סיכון"


def test_nested_attention_block_does_not_start_a_new_section() -> None:
    text = (
        "**דגלי סיכון**\n"
        "*(אינדיקטור בלבד. אינו מהווה אבחנה רפואית)*\n"
        "**גבוה** — פתיחת זיכרון ליבה עם הצפה משמעותית.\n\n"
        "**לתשומת לב**\n"
        "נדרשת זמינות השבוע; מעקב הדוק אחר שינה."
    )

    parsed = parse_summary_sections(text)

    assert parsed is not None
    assert parsed.session_risk_flags is not None
    assert parsed.session_risk_flags.level == "גבוה"
    assert parsed.session_risk_flags.note == "פתיחת זיכרון ליבה עם הצפה משמעותית."
    assert parsed.session_risk_flags.attention == "נדרשת זמינות השבוע; מעקב הדוק אחר שינה."


def test_missing_sections_stay_empty_rather_than_guessed() -> None:
    parsed = parse_summary_sections("## נושאים מרכזיים\n- חרדה")

    assert parsed is not None
    assert parsed.session_main_topics == ["חרדה"]
    assert parsed.insights is None
    assert parsed.session_summary is None
    assert parsed.session_risk_flags is None
    assert parsed.therapist_interventions == []
    assert parsed.follow_up == []


@pytest.mark.parametrize(
    "text",
    [
        "",
        "   \n  ",
        "טקסט חופשי בלי שום כותרת מוכרת.",
        "## כותרת שלא מוכרת\nתוכן כלשהו.",
    ],
)
def test_returns_none_when_no_section_is_recognised(text: str) -> None:
    assert parse_summary_sections(text) is None


def test_every_seeded_summary_splits_into_all_four_sections() -> None:
    """The demo corpus is what the frontend renders — none of it may fall back to text."""
    seeded = sorted(OUTPUT_DIR.glob("*.json"))
    assert seeded, "no seeded patients found"

    for path in seeded:
        sessions = json.loads(path.read_text(encoding="utf-8"))["sessions"]
        for session in sessions:
            parsed = parse_summary_sections(session["summary"])
            where = f"{path.name} session {session['n']}"
            assert parsed is not None, where
            assert parsed.title, where
            assert parsed.insights, where
            assert parsed.session_summary, where
            assert parsed.session_main_topics, where
            assert parsed.session_risk_flags is not None, where
            assert parsed.session_risk_flags.level, where
            assert parsed.session_risk_flags.note, where
