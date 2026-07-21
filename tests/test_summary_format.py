from summaries.format import normalize_summary_output, summary_json_to_markdown


def test_summary_json_to_markdown_uses_hebrew_headings() -> None:
    md = summary_json_to_markdown(
        {
            "main_topics": "חרדה בעבודה",
            "therapist_interventions": "שיקוף ונשימה",
            "risk_signs": "לא נאמרו אמירות מפורשות של סיכון",
            "follow_up": ["שינה", "ויסות"],
        }
    )
    assert "## נושאים מרכזיים" in md
    assert "חרדה בעבודה" in md
    assert "## המשך ומעקב" in md
    assert "- שינה" in md
    assert "- ויסות" in md


def test_summary_json_to_markdown_splits_prose_into_bullets() -> None:
    md = summary_json_to_markdown(
        {
            "main_topics": "המטופל הגיע עם חרדה בעבודה. נדונו דפוסי שינה; שימוש בכלי ויסות.",
            "therapist_interventions": "שוקף החרדה. חודדה טכניקת נשימה.",
            "risk_signs": "לא נאמרו אמירות מפורשות של סיכון",
            "follow_up": ["מעקב שינה"],
        }
    )
    assert "- המטופל הגיע עם חרדה בעבודה." in md
    assert "- נדונו דפוסי שינה" in md
    assert "- שימוש בכלי ויסות." in md
    assert "- שוקף החרדה." in md
    assert "- חודדה טכניקת נשימה." in md
    # Risk stays as a single prose line (not bulleted).
    assert "- לא נאמרו" not in md


def test_normalize_summary_output_parses_json() -> None:
    raw = """\
{
  "main_topics": "נושא",
  "therapist_interventions": "התערבות",
  "risk_signs": "לא נאמרו אמירות מפורשות של סיכון",
  "follow_up": ["מעקב"]
}
"""
    md = normalize_summary_output(raw)
    assert md.startswith("## נושאים מרכזיים")
    assert "- מעקב" in md


def test_normalize_summary_output_keeps_markdown_passthrough() -> None:
    raw = "## נושאים מרכזיים\nחרדה במהלך השבוע."
    assert normalize_summary_output(raw) == raw


def test_normalize_summary_output_recovers_nested_object() -> None:
    """Broken outer JSON + clean inner summary object (seen in production)."""
    raw = (
        "{\n"
        '  "main_topics": "עברית לא סגורה PTSD描述：\n\n'
        "{\n"
        '  "main_topics": "שינה וחרדה",\n'
        '  "therapist_interventions": "נשימה",\n'
        '  "risk_signs": "לא נאמרו אמירות מפורשות של סיכון",\n'
        '  "follow_up": ["מעקב שינה"]\n'
        "}\n"
    )
    md = normalize_summary_output(raw)
    assert md.startswith("## נושאים מרכזיים")
    assert "שינה וחרדה" in md
    assert "- מעקב שינה" in md


def test_normalize_summary_output_repairs_missing_commas_in_follow_up() -> None:
    """Ollama often emits adjacent strings in follow_up without commas."""
    raw = """\
{
  "main_topics": "יצירת ברית, הערכה ראשונית",
  "therapist_interventions": "ניסיון לברר עבר",
  "risk_signs": "",
  "follow_up": [
    "לשכוח את העבר במובן של לא שכח, וללמד לחיות איתו"
    "להתבונן מתי המטופל/ת מרגיש דחף פיזי לברוח"
  ]
}
"""
    md = normalize_summary_output(raw)
    assert md.startswith("## נושאים מרכזיים")
    assert "יצירת ברית" in md
    assert "עבר" in md or "דחף" in md
