import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from calendar_events.orm import CalendarEventRecord
from summaries.models import ReadyMeetingSummary, StoredSummary
from summaries.orm import SummaryRecord


def to_summary(record: SummaryRecord) -> StoredSummary:
    return StoredSummary(
        user_id=record.user_id,
        id=record.id,
        meeting_id=record.meeting_id,
        status=record.status,  # type: ignore[arg-type]
        text=record.text,
        model=record.model,
        error=record.error,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


class SummaryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def _record_for(
        self,
        user_id: uuid.UUID,
        meeting_id: uuid.UUID,
    ) -> SummaryRecord | None:
        result = await self._session.execute(
            select(SummaryRecord).where(
                SummaryRecord.user_id == user_id,
                SummaryRecord.meeting_id == meeting_id,
            )
        )
        return result.scalar_one_or_none()

    async def _save(self, record: SummaryRecord) -> StoredSummary:
        self._session.add(record)
        await self._session.commit()
        await self._session.refresh(record)
        return to_summary(record)

    async def create_pending(
        self,
        user_id: uuid.UUID,
        meeting_id: uuid.UUID,
        *,
        model: str = "",
    ) -> StoredSummary:
        record = await self._record_for(user_id, meeting_id)
        if record is None:
            record = SummaryRecord(
                user_id=user_id,
                meeting_id=meeting_id,
                status="pending",
                model=model,
            )
        else:
            # Re-requesting a summary resets the row rather than stacking a second one.
            record.status = "pending"
            record.text = None
            record.error = None
        return await self._save(record)

    async def mark_running(self, user_id: uuid.UUID, meeting_id: uuid.UUID) -> StoredSummary:
        record = await self._record_for(user_id, meeting_id)
        if record is None:
            record = SummaryRecord(user_id=user_id, meeting_id=meeting_id)
        record.status = "running"
        return await self._save(record)

    async def mark_ready(
        self,
        user_id: uuid.UUID,
        meeting_id: uuid.UUID,
        *,
        text: str,
        model: str,
    ) -> StoredSummary:
        record = await self._record_for(user_id, meeting_id)
        if record is None:
            record = SummaryRecord(user_id=user_id, meeting_id=meeting_id)
        record.status = "ready"
        record.text = text
        record.model = model
        record.error = None
        return await self._save(record)

    async def mark_failed(
        self,
        user_id: uuid.UUID,
        meeting_id: uuid.UUID,
        *,
        error: str,
    ) -> StoredSummary:
        record = await self._record_for(user_id, meeting_id)
        if record is None:
            record = SummaryRecord(user_id=user_id, meeting_id=meeting_id)
        record.status = "failed"
        record.error = error
        return await self._save(record)

    async def get_by_meeting_id(
        self,
        user_id: uuid.UUID,
        meeting_id: uuid.UUID,
    ) -> StoredSummary | None:
        record = await self._record_for(user_id, meeting_id)
        return to_summary(record) if record else None

    async def list_running(self) -> list[StoredSummary]:
        result = await self._session.execute(
            select(SummaryRecord).where(SummaryRecord.status == "running")
        )
        return [to_summary(record) for record in result.scalars().all()]

    async def list_ready_for_patient(
        self,
        user_id: uuid.UUID,
        patient_id: uuid.UUID,
        *,
        limit: int = 8,
    ) -> list[ReadyMeetingSummary]:
        """Ready session summaries for a patient, newest meetings first."""
        stmt = (
            select(SummaryRecord, CalendarEventRecord.start_at)
            .join(
                CalendarEventRecord,
                (CalendarEventRecord.user_id == SummaryRecord.user_id)
                & (CalendarEventRecord.id == SummaryRecord.meeting_id),
            )
            .where(
                CalendarEventRecord.user_id == user_id,
                CalendarEventRecord.patient_id == patient_id,
                SummaryRecord.status == "ready",
                SummaryRecord.text.is_not(None),
            )
            .order_by(CalendarEventRecord.start_at.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        out: list[ReadyMeetingSummary] = []
        for summary, start_at in result.all():
            text = summary.text or ""
            if not text.strip():
                continue
            out.append(
                ReadyMeetingSummary(
                    meeting_id=summary.meeting_id,
                    start_at=start_at,
                    text=text,
                )
            )
        return out

    async def list_ready_before_meeting(
        self,
        user_id: uuid.UUID,
        patient_id: uuid.UUID,
        *,
        before_start_at: datetime,
        limit: int = 8,
    ) -> list[ReadyMeetingSummary]:
        """Ready summaries for past meetings only (before the target meeting)."""
        stmt = (
            select(SummaryRecord, CalendarEventRecord.start_at)
            .join(
                CalendarEventRecord,
                (CalendarEventRecord.user_id == SummaryRecord.user_id)
                & (CalendarEventRecord.id == SummaryRecord.meeting_id),
            )
            .where(
                CalendarEventRecord.user_id == user_id,
                CalendarEventRecord.patient_id == patient_id,
                CalendarEventRecord.start_at < before_start_at,
                SummaryRecord.status == "ready",
                SummaryRecord.text.is_not(None),
            )
            .order_by(CalendarEventRecord.start_at.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        out: list[ReadyMeetingSummary] = []
        for summary, start_at in result.all():
            text = summary.text or ""
            if not text.strip():
                continue
            out.append(
                ReadyMeetingSummary(
                    meeting_id=summary.meeting_id,
                    start_at=start_at,
                    text=text,
                )
            )
        return out
