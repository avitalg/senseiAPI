import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class PatientRecord(Base):
    __tablename__ = "patients"

    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255))
    phone: Mapped[str] = mapped_column(String(32))
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    archived: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    archived_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
