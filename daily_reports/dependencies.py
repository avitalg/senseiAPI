from calendar_events.repository import CalendarEventRepository
from core.config import Settings
from core.database import SessionDep, SettingsDep
from daily_reports.repository import DailyMeetingReportRepository
from daily_reports.service import (
    MEETING_REPORT_WAIT_GRACE_SECONDS,
    DailyMeetingReportService,
    build_daily_report_service,
    build_daily_synthesizer,
)
from patients.repository import PatientRepository
from reports.dependencies import build_report_service


def build_service(session: SessionDep, settings: Settings) -> DailyMeetingReportService:
    return build_daily_report_service(
        reports=DailyMeetingReportRepository(session),
        calendar=CalendarEventRepository(session),
        patients=PatientRepository(session),
        meeting_reports=build_report_service(session, settings),
        synthesizer=build_daily_synthesizer(settings),
        meeting_report_wait_timeout_seconds=(
            settings.ollama_timeout_seconds + MEETING_REPORT_WAIT_GRACE_SECONDS
        ),
    )


def get_daily_report_service(
    session: SessionDep,
    settings: SettingsDep,
) -> DailyMeetingReportService:
    return build_service(session, settings)
