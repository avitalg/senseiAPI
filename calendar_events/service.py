import uuid
from datetime import datetime

from calendar_events.models import CalendarEvent
from calendar_events.repository import CalendarEventRepository


class CalendarEventService:
    """Business logic for scheduled therapy meetings (calendar_events rows)."""

    def __init__(self, repository: CalendarEventRepository) -> None:
        self._repository = repository

    async def add_event(
        self,
        *,
        user_id: uuid.UUID,
        title: str,
        start_at: datetime,
        end_at: datetime,
        description: str | None = None,
        patient_id: uuid.UUID | None = None,
    ) -> CalendarEvent:
        return await self._repository.create(
            user_id=user_id,
            title=title,
            description=description,
            start_at=start_at,
            end_at=end_at,
            patient_id=patient_id,
        )

    async def list_events(
        self,
        *,
        user_id: uuid.UUID,
        from_at: datetime,
        to_at: datetime,
    ) -> list[CalendarEvent]:
        return await self._repository.list_all(
            user_id=user_id,
            from_at=from_at,
            to_at=to_at,
        )

    async def get_meeting(self, user_id: uuid.UUID, meeting_id: uuid.UUID) -> CalendarEvent:
        return await self._repository.get_meeting(user_id, meeting_id)

    async def update_meeting(
        self,
        user_id: uuid.UUID,
        meeting_id: uuid.UUID,
        updates: dict[str, object],
    ) -> CalendarEvent:
        return await self._repository.update_meeting(user_id, meeting_id, updates)

    async def delete_meeting(self, user_id: uuid.UUID, meeting_id: uuid.UUID) -> None:
        await self._repository.delete_meeting(user_id, meeting_id)

    async def get_event(self, user_id: uuid.UUID, event_id: uuid.UUID) -> CalendarEvent:
        return await self.get_meeting(user_id, event_id)

    async def update_event(
        self,
        user_id: uuid.UUID,
        event_id: uuid.UUID,
        updates: dict[str, object],
    ) -> CalendarEvent:
        return await self.update_meeting(user_id, event_id, updates)

    async def delete_event(self, user_id: uuid.UUID, event_id: uuid.UUID) -> None:
        await self.delete_meeting(user_id, event_id)
