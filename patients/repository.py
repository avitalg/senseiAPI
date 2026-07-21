import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from patients.models import Patient, PatientNotFoundError
from patients.orm import PatientRecord


def _to_patient(record: PatientRecord) -> Patient:
    return Patient(
        user_id=record.user_id,
        id=record.id,
        name=record.name,
        phone=record.phone,
        email=record.email,
        created_at=record.created_at,
        archived=bool(record.archived),
        archived_at=record.archived_at,
    )


class PatientRepository:
    """Persists patients in PostgreSQL."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        user_id: uuid.UUID,
        name: str,
        phone: str,
        email: str | None = None,
    ) -> Patient:
        record = PatientRecord(user_id=user_id, name=name, phone=phone, email=email)
        self._session.add(record)
        await self._session.commit()
        await self._session.refresh(record)
        return _to_patient(record)

    async def list_all(self, user_id: uuid.UUID, *, archived: bool = False) -> list[Patient]:
        result = await self._session.execute(
            select(PatientRecord)
            .where(
                PatientRecord.user_id == user_id,
                PatientRecord.archived.is_(archived),
            )
            .order_by(PatientRecord.created_at.desc())
        )
        return [_to_patient(record) for record in result.scalars().all()]

    async def get(self, user_id: uuid.UUID, patient_id: uuid.UUID) -> Patient:
        result = await self._session.execute(
            select(PatientRecord).where(
                PatientRecord.user_id == user_id,
                PatientRecord.id == patient_id,
            )
        )
        record = result.scalar_one_or_none()
        if record is None:
            raise PatientNotFoundError(patient_id)
        return _to_patient(record)

    async def update(
        self,
        user_id: uuid.UUID,
        patient_id: uuid.UUID,
        updates: dict[str, object],
    ) -> Patient:
        result = await self._session.execute(
            select(PatientRecord).where(
                PatientRecord.user_id == user_id,
                PatientRecord.id == patient_id,
            )
        )
        record = result.scalar_one_or_none()
        if record is None:
            raise PatientNotFoundError(patient_id)
        if "phone" in updates:
            record.phone = str(updates["phone"])
        if "email" in updates:
            email_value = updates["email"]
            record.email = None if email_value is None else str(email_value)
        if "archived" in updates:
            archived = bool(updates["archived"])
            record.archived = archived
            if archived:
                if record.archived_at is None:
                    record.archived_at = datetime.now(UTC)
            else:
                record.archived_at = None
        await self._session.commit()
        await self._session.refresh(record)
        return _to_patient(record)

    async def delete(self, user_id: uuid.UUID, patient_id: uuid.UUID) -> None:
        result = await self._session.execute(
            select(PatientRecord).where(
                PatientRecord.user_id == user_id,
                PatientRecord.id == patient_id,
            )
        )
        record = result.scalar_one_or_none()
        if record is None:
            raise PatientNotFoundError(patient_id)
        await self._session.delete(record)
        await self._session.commit()
