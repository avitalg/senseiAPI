"""Seed the database with therapy patients and their sessions.

Every ``seeds/patients/*.json`` file describes one patient and their therapy
sessions. For each session this loader inserts a calendar event with a matching
transcript (the therapist's dictated note) and a session summary, using the
project ORM. Row ids are deterministic (uuid5 keyed by the patient slug), so
re-running upserts the same rows instead of creating duplicates.

Run:
    .venv/bin/python -m seeds.load
"""

import asyncio
import json
import uuid
from datetime import datetime
from pathlib import Path

from core.config import Settings
from core.database import get_sessionmaker, init_database

# Importing the ORM modules registers their tables on Base.metadata for init_database.
from auth.orm import UserRecord  # noqa: F401
from calendar_events.orm import CalendarEventRecord
from patients.orm import PatientRecord
from summaries.orm import SummaryRecord
from transcripts.orm import TranscriptRecord

PATIENTS_DIR = Path(__file__).with_name("patients")

# Stable namespace so every row's id is reproducible across runs.
SEED_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "senseiapi:seed")


def _sid(*parts: str) -> uuid.UUID:
    return uuid.uuid5(SEED_NAMESPACE, ":".join(parts))


def _load_patient_files() -> list[dict]:
    files = sorted(PATIENTS_DIR.glob("*.json"))
    if not files:
        raise SystemExit(f"No patient seed files found in {PATIENTS_DIR}")
    return [json.loads(f.read_text(encoding="utf-8")) for f in files]


async def _seed_patient(session, data: dict) -> int:
    slug = data["slug"]
    therapist_id = uuid.UUID(data["therapist_id"])
    sessions = data["sessions"]
    patient_id = _sid("patient", slug)
    first_start = datetime.fromisoformat(sessions[0]["start_at"])

    await session.merge(
        PatientRecord(
            id=patient_id,
            name=data["name"],
            phone=data["phone"],
            email=data.get("email"),
            created_at=first_start,
        )
    )

    for s in sessions:
        n = str(s["n"])
        meeting_id = _sid("meeting", slug, n)
        start_at = datetime.fromisoformat(s["start_at"])
        end_at = datetime.fromisoformat(s["end_at"])

        await session.merge(
            CalendarEventRecord(
                id=meeting_id,
                title=s["title"],
                description=None,
                start_at=start_at,
                end_at=end_at,
                created_at=start_at,
                therapist_id=therapist_id,
                patient_id=patient_id,
            )
        )
        await session.merge(
            TranscriptRecord(
                id=_sid("transcript", slug, n),
                meeting_id=meeting_id,
                raw_text=s["transcript"],
                diarized_segments=[],
                language="he",
                created_at=start_at,
            )
        )
        await session.merge(
            SummaryRecord(
                id=_sid("summary", slug, n),
                meeting_id=meeting_id,
                status="ready",
                text=s["summary"],
                model="seed",
                error=None,
                created_at=start_at,
                updated_at=start_at,
            )
        )

    return len(sessions)


async def load() -> None:
    patients = _load_patient_files()

    settings = Settings()
    if not settings.database_url:
        raise SystemExit("DATABASE_URL is not set — cannot seed.")

    await init_database(settings)
    sessionmaker = get_sessionmaker(settings.database_url)

    async with sessionmaker() as session:
        for data in patients:
            count = await _seed_patient(session, data)
            print(f"Seeded {data['name']} ({data['slug']}) with {count} sessions.")
        await session.commit()

    print(f"Done — {len(patients)} patients seeded.")


if __name__ == "__main__":
    asyncio.run(load())
