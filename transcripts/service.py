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
    TranscriptNotFoundError,
    TranscriptPatientMismatchError,
)
from transcripts.orm import TranscriptRecord
from transcripts.repository import TranscriptRepository, to_transcript


class TranscriptService:
    """Persists a transcript 1:1 with an existing calendar event (the therapy meeting)."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = TranscriptRepository(session)

    async def _validate_meeting_and_patient(
        self,
        *,
        meeting_id: uuid.UUID,
        patient_id: uuid.UUID | None = None,
    ) -> None:
        meeting = await self._session.get(CalendarEventRecord, meeting_id)
        if meeting is None:
            raise CalendarEventNotFoundError(meeting_id)

        if patient_id is not None:
            patient = await self._session.get(PatientRecord, patient_id)
            if patient is None:
                raise PatientNotFoundError(patient_id)
            if meeting.patient_id is not None and meeting.patient_id != patient_id:
                raise TranscriptPatientMismatchError(meeting_id, patient_id)

    async def _existing_for_meeting(self, meeting_id: uuid.UUID) -> TranscriptRecord | None:
        result = await self._session.execute(
            select(TranscriptRecord).where(TranscriptRecord.meeting_id == meeting_id)
        )
        return result.scalar_one_or_none()

    async def save_for_upload(
        self,
        *,
        meeting_id: uuid.UUID,
        patient_id: uuid.UUID | None = None,
        raw_text: str,
        language: str = "he",
        diarized_segments: list[dict[str, Any]] | None = None,
    ) -> StoredTranscript:
        await self._validate_meeting_and_patient(meeting_id=meeting_id, patient_id=patient_id)

        if await self._existing_for_meeting(meeting_id) is not None:
            raise TranscriptAlreadyExistsError(meeting_id)

        record = TranscriptRecord(
            meeting_id=meeting_id,
            raw_text=raw_text,
            language=language or "he",
            diarized_segments=diarized_segments or [],
        )
        self._session.add(record)
        await self._session.commit()
        await self._session.refresh(record)
        return to_transcript(record)

    async def append_for_upload(
        self,
        *,
        meeting_id: uuid.UUID,
        patient_id: uuid.UUID | None = None,
        raw_text: str,
        language: str = "he",
        diarized_segments: list[dict[str, Any]] | None = None,
    ) -> StoredTranscript:
        await self._validate_meeting_and_patient(meeting_id=meeting_id, patient_id=patient_id)

        existing = await self._existing_for_meeting(meeting_id)
        if existing is None:
            raise TranscriptNotFoundError(meeting_id)

        new_chunk = raw_text.strip()
        merged_text = existing.raw_text.rstrip()
        if new_chunk:
            merged_text = (merged_text + "\n\n" + new_chunk) if merged_text else new_chunk

        merged_segments = list(existing.diarized_segments or [])
        if diarized_segments:
            merged_segments.extend(diarized_segments)

        updated = await self._repo.update(
            meeting_id,
            raw_text=merged_text,
            language=language or existing.language,
            diarized_segments=merged_segments,
        )
        assert updated is not None
        return updated

    async def replace_for_upload(
        self,
        *,
        meeting_id: uuid.UUID,
        patient_id: uuid.UUID | None = None,
        raw_text: str,
        language: str = "he",
        diarized_segments: list[dict[str, Any]] | None = None,
    ) -> StoredTranscript:
        await self._validate_meeting_and_patient(meeting_id=meeting_id, patient_id=patient_id)
        await self._repo.delete_by_meeting_id(meeting_id)
        return await self._repo.create(
            meeting_id=meeting_id,
            raw_text=raw_text,
            language=language or "he",
            diarized_segments=diarized_segments,
        )

    async def get_by_meeting_id(self, meeting_id: uuid.UUID) -> StoredTranscript | None:
        return await self._repo.get_by_meeting_id(meeting_id)
