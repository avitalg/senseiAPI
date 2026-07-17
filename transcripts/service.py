import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from calendar_events.models import CalendarEventNotFoundError
from calendar_events.orm import CalendarEventRecord
from patients.models import PatientNotFoundError
from patients.orm import PatientRecord
from transcripts.models import (
    StoredTranscript,
    TranscriptAlreadyExistsError,
    TranscriptPatientMismatchError,
)
from transcripts.orm import TranscriptRecord
from transcripts.repository import to_transcript


class TranscriptService:
    """Persists a transcript 1:1 with an existing calendar event (the therapy meeting)."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save_for_upload(
        self,
        *,
        user_id: uuid.UUID,
        meeting_id: uuid.UUID,
        patient_id: uuid.UUID | None = None,
        raw_text: str,
        language: str = "he",
        diarized_segments: list[dict[str, Any]] | None = None,
    ) -> StoredTranscript:
        meeting_result = await self._session.execute(
            select(CalendarEventRecord).where(
                CalendarEventRecord.user_id == user_id,
                CalendarEventRecord.id == meeting_id,
            )
        )
        meeting = meeting_result.scalar_one_or_none()
        if meeting is None:
            raise CalendarEventNotFoundError(meeting_id)

        if patient_id is not None:
            patient_result = await self._session.execute(
                select(PatientRecord).where(
                    PatientRecord.user_id == user_id,
                    PatientRecord.id == patient_id,
                )
            )
            patient = patient_result.scalar_one_or_none()
            if patient is None:
                raise PatientNotFoundError(patient_id)
            if meeting.patient_id is not None and meeting.patient_id != patient_id:
                raise TranscriptPatientMismatchError(meeting_id, patient_id)

        result = await self._session.execute(
            select(TranscriptRecord).where(
                TranscriptRecord.user_id == user_id,
                TranscriptRecord.meeting_id == meeting_id,
            )
        )
        if result.scalar_one_or_none() is not None:
            raise TranscriptAlreadyExistsError(meeting_id)

        record = TranscriptRecord(
            user_id=user_id,
            meeting_id=meeting.id,
            raw_text=raw_text,
            language=language or "he",
            diarized_segments=diarized_segments or [],
        )
        self._session.add(record)
        await self._session.commit()
        await self._session.refresh(record)
        return to_transcript(record)
