import uuid

from patients.models import Patient
from patients.repository import PatientRepository


class PatientService:
    """Business logic for patient management."""

    def __init__(self, repository: PatientRepository) -> None:
        self._repository = repository

    async def add_patient(
        self,
        *,
        user_id: uuid.UUID,
        name: str,
        phone: str,
        email: str | None = None,
    ) -> Patient:
        return await self._repository.create(
            user_id=user_id,
            name=name,
            phone=phone,
            email=email,
        )

    async def list_patients(self, user_id: uuid.UUID) -> list[Patient]:
        return await self._repository.list_all(user_id)

    async def get_patient(self, user_id: uuid.UUID, patient_id: uuid.UUID) -> Patient:
        return await self._repository.get(user_id, patient_id)

    async def update_patient(
        self,
        user_id: uuid.UUID,
        patient_id: uuid.UUID,
        updates: dict[str, object],
    ) -> Patient:
        return await self._repository.update(user_id, patient_id, updates)

    async def delete_patient(self, user_id: uuid.UUID, patient_id: uuid.UUID) -> None:
        await self._repository.delete(user_id, patient_id)
