"""Seed the database with the patient סימבה and five therapy sessions.

Each session becomes a calendar event with a matching transcript (the therapist's
dictated note) and a session summary. Rows use deterministic UUIDs (uuid5), so the
loader is idempotent — re-running updates the existing rows instead of duplicating.

Run:
    .venv/bin/python -m seeds.load_simba
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

SEED_FILE = Path(__file__).with_name("simba_seed.json")

# Stable namespace so every row's id is reproducible across runs.
SEED_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "senseiapi:seed:simba")


def _sid(*parts: str) -> uuid.UUID:
    return uuid.uuid5(SEED_NAMESPACE, ":".join(parts))


async def load() -> None:
    data = json.loads(SEED_FILE.read_text(encoding="utf-8"))
    therapist_id = uuid.UUID(data["therapist_id"])
    patient_info = data["patient"]
    sessions = data["sessions"]

    settings = Settings()
    if not settings.database_url:
        raise SystemExit("DATABASE_URL is not set — cannot seed.")

    await init_database(settings)
    sessionmaker = get_sessionmaker(settings.database_url)

    patient_id = _sid("patient")
    first_start = datetime.fromisoformat(sessions[0]["start_at"])

    async with sessionmaker() as session:
        await session.merge(
            PatientRecord(
                id=patient_id,
                name=patient_info["name"],
                phone=patient_info["phone"],
                email=patient_info.get("email"),
                created_at=first_start,
            )
        )

        for s in sessions:
            n = str(s["n"])
            meeting_id = _sid("meeting", n)
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
                    id=_sid("transcript", n),
                    meeting_id=meeting_id,
                    raw_text=s["transcript"],
                    diarized_segments=[],
                    language="he",
                    created_at=start_at,
                )
            )
            await session.merge(
                SummaryRecord(
                    id=_sid("summary", n),
                    meeting_id=meeting_id,
                    status="ready",
                    text=s["summary"],
                    model="seed",
                    error=None,
                    created_at=start_at,
                    updated_at=start_at,
                )
            )

        await session.commit()

    print(f"Seeded patient {patient_info['name']} ({patient_id}) with {len(sessions)} sessions.")


if __name__ == "__main__":
    asyncio.run(load())
