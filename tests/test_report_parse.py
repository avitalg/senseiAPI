from reports.parse import (
    FOLLOWUP_HEADING,
    bullets_under_heading,
    parse_report_markdown,
    parse_report_output,
)


def test_parse_splits_three_hebrew_sections() -> None:
    text = """\
## סקירה מהירה
שיפור כללי בין הפגישות.

## שינויים ומגמות
- שיפור בוויסות
- עלייה בחרדה לקראת אירועים

## נושאים פתוחים לפגישה הבאה
- לעבד את הפחד מהפעם הבאה
- לבדוק שינה
"""
    intro, changes, open_topics = parse_report_markdown(text)
    assert "שיפור כללי" in intro
    assert changes == ["שיפור בוויסות", "עלייה בחרדה לקראת אירועים"]
    assert open_topics == ["לעבד את הפחד מהפעם הבאה", "לבדוק שינה"]


def test_parse_json_structure() -> None:
    raw = """\
{
  "intro": "מצב יציב עם חשש קל.",
  "changes": ["שיפור בוויסות", "פחות הימנעות"],
  "open_topics": ["לחזור לשינה", "לחזק מסוגלות"]
}
"""
    intro, changes, open_topics = parse_report_output(raw)
    assert intro == "מצב יציב עם חשש קל."
    assert changes == ["שיפור בוויסות", "פחות הימנעות"]
    assert open_topics == ["לחזור לשינה", "לחזק מסוגלות"]


def test_parse_json_inside_fence() -> None:
    raw = """```json
{"intro": "סקירה", "changes": ["א"], "open_topics": ["ב"]}
```"""
    intro, changes, open_topics = parse_report_output(raw)
    assert intro == "סקירה"
    assert changes == ["א"]
    assert open_topics == ["ב"]


def test_parse_accepts_short_open_topics_heading() -> None:
    text = """\
## סקירה מהירה
מצב יציב.

## שינויים ומגמות
- שיפור קל

## נושאים פתוחים
- לחזור לחרדה בעבודה
- לבדוק רשת תמיכה
"""
    intro, changes, open_topics = parse_report_markdown(text)
    assert "מצב יציב" in intro
    assert changes == ["שיפור קל"]
    assert open_topics == ["לחזור לחרדה בעבודה", "לבדוק רשת תמיכה"]


def test_parse_accepts_changes_aliases() -> None:
    text = """\
## סקירה מהירה
טוב.

## מה השתנה
- פחות הימנעות

## נושאים להמשך
- תרגול חשיפה
"""
    _, changes, open_topics = parse_report_markdown(text)
    assert changes == ["פחות הימנעות"]
    assert open_topics == ["תרגול חשיפה"]


def test_bullets_under_followup_heading() -> None:
    text = """\
## נושאים מרכזיים
נושא.

## המשך ומעקב
- לחזור לדפוסי שינה
- לחזק כלי ויסות
"""
    assert bullets_under_heading(text, FOLLOWUP_HEADING) == [
        "לחזור לדפוסי שינה",
        "לחזק כלי ויסות",
    ]


def test_parse_failure_keeps_raw_text_as_intro() -> None:
    raw = "טקסט חופשי בלי כותרות בכלל"
    intro, changes, open_topics = parse_report_markdown(raw)
    assert intro == raw
    assert changes == []
    assert open_topics == []
