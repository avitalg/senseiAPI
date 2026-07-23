import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest

from seeds.generate import (
    CONTACTS,
    OUTPUT_DIR,
    SEED_USER_ID,
    SESSIONS_PER_PATIENT,
    TITLE_MAX_LENGTH,
)

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
    assert set(CONTACTS) >= EXPECTED_SLUGS


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
    starts = [session["start_at"] for path in _seed_files() for session in _load(path)["sessions"]]

    assert len(starts) == len(set(starts))
