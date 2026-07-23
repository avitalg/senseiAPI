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
