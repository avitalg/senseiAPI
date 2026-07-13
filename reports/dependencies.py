from core.config import Settings, get_settings
from core.database import SessionDep, SettingsDep
from reports.repository import NextMeetingReportRepository
from reports.service import NextMeetingReportService, build_synthesizer
from reports.synthesizer import ReportSynthesizer
from summaries.repository import SummaryRepository


def get_report_synthesizer(settings: Settings) -> ReportSynthesizer:
    return build_synthesizer(settings)


def build_report_service(session: SessionDep, settings: Settings) -> NextMeetingReportService:
    return NextMeetingReportService(
        reports=NextMeetingReportRepository(session),
        summaries=SummaryRepository(session),
        synthesizer=get_report_synthesizer(settings),
    )


def get_report_reader(session: SessionDep) -> NextMeetingReportRepository:
    return NextMeetingReportRepository(session)


def get_report_service(session: SessionDep, settings: SettingsDep) -> NextMeetingReportService:
    return build_report_service(session, settings)


__all__ = [
    "build_report_service",
    "get_report_reader",
    "get_report_service",
    "get_report_synthesizer",
    "get_settings",
]
