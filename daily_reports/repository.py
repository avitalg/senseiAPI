import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from daily_reports.models import StoredDailyReport
from daily_reports.orm import DailyMeetingReportRecord


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


def to_daily_report(record: DailyMeetingReportRecord) -> StoredDailyReport:
    return StoredDailyReport(
        user_id=record.user_id,
        id=record.id,
        report_date=record.report_date,
        time_zone=record.time_zone,
        status=record.status,  # type: ignore[arg-type]
        meeting_limit=record.meeting_limit,
        meeting_count=record.meeting_count,
        text=record.text,
        source_meeting_ids=_as_uuid_list(record.source_meeting_ids),
        source_report_ids=_as_uuid_list(record.source_report_ids),
        model=record.model,
        prompt_version=record.prompt_version,
        error=record.error,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


class DailyMeetingReportRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def _record_by_id(
        self,
        user_id: uuid.UUID,
        report_id: uuid.UUID,
    ) -> DailyMeetingReportRecord | None:
        result = await self._session.execute(
            select(DailyMeetingReportRecord).where(
                DailyMeetingReportRecord.user_id == user_id,
                DailyMeetingReportRecord.id == report_id,
            )
        )
        return result.scalar_one_or_none()

    async def _record_by_date(
        self,
        user_id: uuid.UUID,
        report_date: date,
    ) -> DailyMeetingReportRecord | None:
        result = await self._session.execute(
            select(DailyMeetingReportRecord).where(
                DailyMeetingReportRecord.user_id == user_id,
                DailyMeetingReportRecord.report_date == report_date,
            )
        )
        return result.scalar_one_or_none()

    async def _save(self, record: DailyMeetingReportRecord) -> StoredDailyReport:
        self._session.add(record)
        await self._session.commit()
        await self._session.refresh(record)
        return to_daily_report(record)

    async def create_pending(
        self,
        user_id: uuid.UUID,
        report_date: date,
        *,
        time_zone: str,
        meeting_limit: int,
    ) -> StoredDailyReport:
        record = await self._record_by_date(user_id, report_date)
        if record is None:
            record = DailyMeetingReportRecord(
                user_id=user_id,
                report_date=report_date,
                time_zone=time_zone,
                meeting_limit=meeting_limit,
            )
        else:
            record.time_zone = time_zone
            record.meeting_limit = meeting_limit
        record.status = "pending"
        record.meeting_count = 0
        record.text = None
        record.source_meeting_ids = []
        record.source_report_ids = []
        record.model = ""
        record.prompt_version = ""
        record.error = None
        return await self._save(record)

    async def mark_running(
        self,
        user_id: uuid.UUID,
        report_id: uuid.UUID,
    ) -> StoredDailyReport:
        record = await self._record_by_id(user_id, report_id)
        if record is None:
            raise ValueError(f"no daily report row {report_id!r}")
        record.status = "running"
        return await self._save(record)

    async def mark_ready(
        self,
        user_id: uuid.UUID,
        report_id: uuid.UUID,
        *,
        text: str,
        meeting_count: int,
        source_meeting_ids: list[uuid.UUID],
        source_report_ids: list[uuid.UUID],
        model: str,
        prompt_version: str,
    ) -> StoredDailyReport:
        record = await self._record_by_id(user_id, report_id)
        if record is None:
            raise ValueError(f"no daily report row {report_id!r}")
        record.status = "ready"
        record.text = text
        record.meeting_count = meeting_count
        record.source_meeting_ids = [str(item) for item in source_meeting_ids]
        record.source_report_ids = [str(item) for item in source_report_ids]
        record.model = model
        record.prompt_version = prompt_version
        record.error = None
        return await self._save(record)

    async def mark_failed(
        self,
        user_id: uuid.UUID,
        report_id: uuid.UUID,
        *,
        error: str,
    ) -> StoredDailyReport:
        record = await self._record_by_id(user_id, report_id)
        if record is None:
            raise ValueError(f"no daily report row {report_id!r}")
        record.status = "failed"
        record.error = error
        return await self._save(record)

    async def get_by_id(
        self,
        user_id: uuid.UUID,
        report_id: uuid.UUID,
    ) -> StoredDailyReport | None:
        record = await self._record_by_id(user_id, report_id)
        return to_daily_report(record) if record else None

    async def get_by_date(
        self,
        user_id: uuid.UUID,
        report_date: date,
    ) -> StoredDailyReport | None:
        record = await self._record_by_date(user_id, report_date)
        return to_daily_report(record) if record else None

    async def list_running(self) -> list[StoredDailyReport]:
        result = await self._session.execute(
            select(DailyMeetingReportRecord).where(DailyMeetingReportRecord.status == "running")
        )
        return [to_daily_report(record) for record in result.scalars().all()]
