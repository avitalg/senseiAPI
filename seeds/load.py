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
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

# Importing the ORM modules registers their tables on Base.metadata for init_database.
from auth.orm import UserRecord  # noqa: F401
from calendar_events.orm import CalendarEventRecord
from core.config import Settings
from core.database import get_sessionmaker, init_database
from patients.orm import PatientRecord
from summaries.orm import SummaryRecord
from transcripts.orm import TranscriptRecord

logger = logging.getLogger(__name__)

PATIENTS_DIR = Path(__file__).with_name("patients")

# Stable namespace so every row's id is reproducible across runs.
SEED_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "senseiapi:seed")

# Mirrors the marker the mock corpus uses for the therapist's private note.
NOTE_PREFIX = "🎙️ הקלטת המטפל (Note): "


def _sid(*parts: str) -> uuid.UUID:
    return uuid.uuid5(SEED_NAMESPACE, ":".join(parts))


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


def _load_patient_files() -> list[dict[str, Any]]:
    files = sorted(PATIENTS_DIR.glob("*.json"))
    if not files:
        raise SystemExit(f"No patient seed files found in {PATIENTS_DIR}")
    return [json.loads(f.read_text(encoding="utf-8")) for f in files]


async def _seed_patient(session: AsyncSession, data: dict[str, Any]) -> int:
    slug = data["slug"]
    user_id = uuid.UUID(data["user_id"])
    sessions = data["sessions"]
    patient_id = _sid("patient", slug)
    first_start = datetime.fromisoformat(sessions[0]["start_at"])

    await session.merge(
        PatientRecord(
            user_id=user_id,
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
                user_id=user_id,
                id=meeting_id,
                title=s["title"],
                description=None,
                start_at=start_at,
                end_at=end_at,
                created_at=start_at,
                patient_id=patient_id,
            )
        )
        await session.merge(
            TranscriptRecord(
                user_id=user_id,
                id=_sid("transcript", slug, n),
                meeting_id=meeting_id,
                raw_text=_raw_text(s),
                diarized_segments=[],
                language="he",
                created_at=start_at,
            )
        )
        await session.merge(
            SummaryRecord(
                user_id=user_id,
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


async def seed_database(settings: Settings) -> int:
    """Idempotently upsert all seed patients and their sessions.

    Assumes the schema already exists (call after ``init_database``). Row ids are
    deterministic, so re-running merges the same rows instead of duplicating them —
    safe to invoke on every startup/deployment. Returns the number of patients seeded.
    """
    if not settings.database_url:
        raise SystemExit("DATABASE_URL is not set — cannot seed.")

    patients = _load_patient_files()
    sessionmaker = get_sessionmaker(settings.database_url)

    async with sessionmaker() as session:
        for data in patients:
            count = await _seed_patient(session, data)
            logger.info("Seeded %s (%s) with %d sessions.", data["name"], data["slug"], count)
        await session.commit()

    logger.info("Done — %d patients seeded.", len(patients))
    return len(patients)


async def load() -> None:
    """CLI entry point: create the schema, then seed."""
    settings = Settings()
    if not settings.database_url:
        raise SystemExit("DATABASE_URL is not set — cannot seed.")
    await init_database(settings)
    await seed_database(settings)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    asyncio.run(load())
