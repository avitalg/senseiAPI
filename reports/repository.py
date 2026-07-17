import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from reports.models import StoredReport
from reports.orm import NextMeetingReportRecord


def _as_str_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    out: list[str] = []
    for item in value:
        if not isinstance(item, str):
            continue
        text = item.strip()
        if text:
            out.append(text)
    return out


def _as_uuid_list(value: object) -> list[uuid.UUID]:
    if not isinstance(value, list):
        return []
    out: list[uuid.UUID] = []
    for item in value:
        try:
            out.append(item if isinstance(item, uuid.UUID) else uuid.UUID(str(item)))
        except (TypeError, ValueError):
            continue
    return out


def to_report(record: NextMeetingReportRecord) -> StoredReport:
    return StoredReport(
        user_id=record.user_id,
        id=record.id,
        patient_id=record.patient_id,
        meeting_id=record.meeting_id,
        status=record.status,  # type: ignore[arg-type]
        intro=record.intro,
        changes=_as_str_list(record.changes),
        open_topics=_as_str_list(record.open_topics),
        source_meeting_ids=_as_uuid_list(record.source_meeting_ids),
        model=record.model,
        error=record.error,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


class NextMeetingReportRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def _record_for(
        self,
        user_id: uuid.UUID,
        meeting_id: uuid.UUID,
    ) -> NextMeetingReportRecord | None:
        result = await self._session.execute(
            select(NextMeetingReportRecord).where(
                NextMeetingReportRecord.user_id == user_id,
                NextMeetingReportRecord.meeting_id == meeting_id,
            )
        )
        return result.scalar_one_or_none()

    async def _save(self, record: NextMeetingReportRecord) -> StoredReport:
        self._session.add(record)
        await self._session.commit()
        await self._session.refresh(record)
        return to_report(record)

    async def create_pending(
        self,
        user_id: uuid.UUID,
        patient_id: uuid.UUID,
        meeting_id: uuid.UUID,
        *,
        model: str = "",
    ) -> StoredReport:
        record = await self._record_for(user_id, meeting_id)
        if record is None:
            record = NextMeetingReportRecord(
                user_id=user_id,
                patient_id=patient_id,
                meeting_id=meeting_id,
                status="pending",
                model=model,
                changes=[],
                open_topics=[],
                source_meeting_ids=[],
            )
        else:
            record.patient_id = patient_id
            record.status = "pending"
            record.intro = None
            record.changes = []
            record.open_topics = []
            record.source_meeting_ids = []
            record.error = None
            if model:
                record.model = model
        return await self._save(record)

    async def mark_running(self, user_id: uuid.UUID, meeting_id: uuid.UUID) -> StoredReport:
        record = await self._record_for(user_id, meeting_id)
        if record is None:
            raise ValueError(f"no report row for meeting {meeting_id!r}")
        record.status = "running"
        return await self._save(record)

    async def mark_ready(
        self,
        user_id: uuid.UUID,
        meeting_id: uuid.UUID,
        *,
        intro: str,
        changes: list[str],
        open_topics: list[str],
        source_meeting_ids: list[uuid.UUID],
        model: str,
    ) -> StoredReport:
        record = await self._record_for(user_id, meeting_id)
        if record is None:
            raise ValueError(f"no report row for meeting {meeting_id!r}")
        record.status = "ready"
        record.intro = intro
        record.changes = list(changes)
        record.open_topics = list(open_topics)
        record.source_meeting_ids = [str(mid) for mid in source_meeting_ids]
        record.model = model
        record.error = None
        return await self._save(record)

    async def mark_failed(
        self,
        user_id: uuid.UUID,
        meeting_id: uuid.UUID,
        *,
        error: str,
    ) -> StoredReport:
        record = await self._record_for(user_id, meeting_id)
        if record is None:
            raise ValueError(f"no report row for meeting {meeting_id!r}")
        record.status = "failed"
        record.error = error
        return await self._save(record)

    async def get_by_meeting_id(
        self,
        user_id: uuid.UUID,
        meeting_id: uuid.UUID,
    ) -> StoredReport | None:
        record = await self._record_for(user_id, meeting_id)
        return to_report(record) if record else None

    async def list_for_patient(
        self,
        user_id: uuid.UUID,
        patient_id: uuid.UUID,
    ) -> list[StoredReport]:
        result = await self._session.execute(
            select(NextMeetingReportRecord)
            .where(
                NextMeetingReportRecord.user_id == user_id,
                NextMeetingReportRecord.patient_id == patient_id,
            )
            .order_by(NextMeetingReportRecord.updated_at.desc())
        )
        return [to_report(record) for record in result.scalars().all()]

    async def list_running(self) -> list[StoredReport]:
        result = await self._session.execute(
            select(NextMeetingReportRecord).where(NextMeetingReportRecord.status == "running")
        )
        return [to_report(record) for record in result.scalars().all()]
