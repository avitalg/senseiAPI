import uuid
from datetime import datetime
from typing import Self

from pydantic import BaseModel, EmailStr, Field, model_validator

from patients.models import Patient


class PatientCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    phone: str = Field(min_length=3, max_length=32)
    email: EmailStr | None = None
    description: str | None = None


class PatientUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    phone: str | None = Field(default=None, min_length=3, max_length=32)
    email: EmailStr | None = None
    description: str | None = None
    archived: bool | None = None

    @model_validator(mode="after")
    def at_least_one_field(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("at least one of name, phone, email, description or archived must be provided")
        return self


class PatientOut(BaseModel):
    id: uuid.UUID
    name: str
    phone: str
    email: str | None
    description: str | None
    archived: bool
    created_at: datetime

    @classmethod
    def from_patient(cls, patient: Patient) -> Self:
        return cls(
            id=patient.id,
            name=patient.name,
            phone=patient.phone,
            email=patient.email,
            description=patient.description,
            archived=patient.archived,
            created_at=patient.created_at,
        )
