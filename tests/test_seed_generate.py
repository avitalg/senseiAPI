import json
from pathlib import Path

import pytest

from seeds.generate import CONTACTS, SEED_USER_ID, build_patient, generate
from seeds.mock_parser import MockParseError

RECORDED = "".join(
    f'## מפגש {n}: כותרת {n}\n\n"תמליל {n}."\n\n🎙️ הקלטת המטפל (Note): "הערה {n}."\n\n---\n\n'
    for n in range(1, 6)
)

UNTITLED_RECORDED = "".join(
    f'## מפגש {n}\n\n"תמליל {n}."\n\n🎙️ הקלטת המטפל (Note): "הערה {n}."\n\n---\n\n'
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
        f'## מפגש {n}: {long_title}\n\n"תמליל {n}."\n\n🎙️ הקלטת המטפל (Note): "הערה {n}."\n\n---\n\n'
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
