import uuid
from datetime import datetime

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from calendar_events.models import CalendarEvent, CalendarEventNotFoundError
from calendar_events.orm import CalendarEventRecord
from patients.models import PatientNotFoundError
from patients.orm import PatientRecord


def _to_event(record: CalendarEventRecord) -> CalendarEvent:
    return CalendarEvent(
        id=record.id,
        title=record.title,
        description=record.description,
        start_at=record.start_at,
        end_at=record.end_at,
        created_at=record.created_at,
        user_id=record.user_id,
        patient_id=record.patient_id,
    )


class CalendarEventRepository:
    """Persists calendar events in PostgreSQL."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        user_id: uuid.UUID,
        title: str,
        start_at: datetime,
        end_at: datetime,
        description: str | None = None,
        patient_id: uuid.UUID | None = None,
    ) -> CalendarEvent:
        await self._ensure_patient_belongs_to_user(user_id, patient_id)
        record = CalendarEventRecord(
            user_id=user_id,
            title=title,
            description=description,
            start_at=start_at,
            end_at=end_at,
            patient_id=patient_id,
        )
        self._session.add(record)
        await self._session.commit()
        await self._session.refresh(record)
        return _to_event(record)

    async def list_all(
        self,
        *,
        user_id: uuid.UUID,
        from_at: datetime,
        to_at: datetime,
    ) -> list[CalendarEvent]:
        statement = select(CalendarEventRecord).where(
            CalendarEventRecord.user_id == user_id,
            or_(
                and_(
                    CalendarEventRecord.start_at >= from_at,
                    CalendarEventRecord.start_at < to_at,
                ),
                and_(
                    CalendarEventRecord.end_at > from_at,
                    CalendarEventRecord.end_at <= to_at,
                ),
                and_(
                    from_at >= CalendarEventRecord.start_at,
                    from_at < CalendarEventRecord.end_at,
                ),
                and_(
                    to_at > CalendarEventRecord.start_at,
                    to_at <= CalendarEventRecord.end_at,
                ),
            ),
        )
        result = await self._session.execute(statement.order_by(CalendarEventRecord.start_at.asc()))
        return [_to_event(record) for record in result.scalars().all()]

    async def get_meeting(self, user_id: uuid.UUID, meeting_id: uuid.UUID) -> CalendarEvent:
        result = await self._session.execute(
            select(CalendarEventRecord).where(
                CalendarEventRecord.id == meeting_id,
                CalendarEventRecord.user_id == user_id,
            )
        )
        record = result.scalar_one_or_none()
        if record is None:
            raise CalendarEventNotFoundError(meeting_id)
        return _to_event(record)

    async def get(self, user_id: uuid.UUID, meeting_id: uuid.UUID) -> CalendarEvent:
        return await self.get_meeting(user_id, meeting_id)

    async def find_active_meeting_for_patient(
        self,
        user_id: uuid.UUID,
        patient_id: uuid.UUID,
        *,
        now: datetime,
    ) -> CalendarEvent | None:
        """Earliest in-progress or upcoming meeting for the patient."""
        result = await self._session.execute(
            select(CalendarEventRecord)
            .where(
                CalendarEventRecord.user_id == user_id,
                CalendarEventRecord.patient_id == patient_id,
                CalendarEventRecord.end_at > now,
            )
            .order_by(CalendarEventRecord.start_at.asc())
            .limit(1)
        )
        record = result.scalar_one_or_none()
        return _to_event(record) if record else None

    async def update_meeting(
        self,
        user_id: uuid.UUID,
        meeting_id: uuid.UUID,
        updates: dict[str, object],
    ) -> CalendarEvent:
        result = await self._session.execute(
            select(CalendarEventRecord).where(
                CalendarEventRecord.user_id == user_id,
                CalendarEventRecord.id == meeting_id,
            )
        )
        record = result.scalar_one_or_none()
        if record is None:
            raise CalendarEventNotFoundError(meeting_id)
        if "title" in updates:
            record.title = str(updates["title"])
        if "description" in updates:
            description_value = updates["description"]
            record.description = None if description_value is None else str(description_value)
        if "start_at" in updates:
            start_at_value = updates["start_at"]
            if isinstance(start_at_value, datetime):
                record.start_at = start_at_value
        if "end_at" in updates:
            end_at_value = updates["end_at"]
            if isinstance(end_at_value, datetime):
                record.end_at = end_at_value
        if "patient_id" in updates:
            patient_id_value = updates["patient_id"]
            if patient_id_value is None or isinstance(patient_id_value, uuid.UUID):
                await self._ensure_patient_belongs_to_user(user_id, patient_id_value)
                record.patient_id = patient_id_value
        await self._session.commit()
        await self._session.refresh(record)
        return _to_event(record)

    async def update(
        self,
        user_id: uuid.UUID,
        meeting_id: uuid.UUID,
        updates: dict[str, object],
    ) -> CalendarEvent:
        return await self.update_meeting(user_id, meeting_id, updates)

    async def delete_meeting(self, user_id: uuid.UUID, meeting_id: uuid.UUID) -> None:
        result = await self._session.execute(
            select(CalendarEventRecord).where(
                CalendarEventRecord.user_id == user_id,
                CalendarEventRecord.id == meeting_id,
            )
        )
        record = result.scalar_one_or_none()
        if record is None:
            raise CalendarEventNotFoundError(meeting_id)
        await self._session.delete(record)
        await self._session.commit()

    async def delete(self, user_id: uuid.UUID, meeting_id: uuid.UUID) -> None:
        await self.delete_meeting(user_id, meeting_id)

    async def _ensure_patient_belongs_to_user(
        self,
        user_id: uuid.UUID,
        patient_id: uuid.UUID | None,
    ) -> None:
        if patient_id is None:
            return
        result = await self._session.execute(
            select(PatientRecord).where(
                PatientRecord.user_id == user_id,
                PatientRecord.id == patient_id,
            )
        )
        if result.scalar_one_or_none() is None:
            raise PatientNotFoundError(patient_id)
