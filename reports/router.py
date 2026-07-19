import logging
import uuid
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response, status
from sqlalchemy.exc import SQLAlchemyError

from auth.router import get_current_user
from auth.schemas import User
from calendar_events.models import CalendarEventNotFoundError
from core.database import SettingsDep
from patients.dependencies import get_patient_service
from patients.models import PatientNotFoundError
from patients.service import PatientService
from reports.dependencies import get_report_service
from reports.models import MeetingPatientMismatchError, NoUpcomingMeetingError, StoredReport
from reports.schemas import MeetingReportListItem, NextMeetingReportResponse
from reports.service import NextMeetingReportService, run_report_generation
from summaries.dependencies import get_summary_reader
from summaries.repository import SummaryRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/patients", tags=["next-meeting-reports"])


async def _ensure_patient_exists(
    user_id: uuid.UUID,
    patient_id: uuid.UUID,
    patients: PatientService,
) -> None:
    try:
        await patients.get_patient(user_id, patient_id)
    except PatientNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except SQLAlchemyError as exc:
        logger.error("failed to load patient for meeting report", exc_info=exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="failed to load patient",
        ) from exc


def _meeting_http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, (CalendarEventNotFoundError, MeetingPatientMismatchError)):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, NoUpcomingMeetingError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail="failed to resolve meeting",
    )


async def _report_response(
    report: StoredReport,
    *,
    user_id: uuid.UUID,
    response: Response | None,
    summaries: SummaryRepository,
    before_start_at: datetime | None = None,
) -> NextMeetingReportResponse:
    if report.status in ("pending", "running"):
        if response is not None:
            response.status_code = status.HTTP_202_ACCEPTED
        return NextMeetingReportResponse.from_report(report)

    excerpt = None
    if report.status == "ready":
        if before_start_at is not None:
            ready = await summaries.list_ready_before_meeting(
                user_id,
                report.patient_id,
                before_start_at=before_start_at,
                limit=1,
            )
        else:
            ready = await summaries.list_ready_for_patient(user_id, report.patient_id, limit=1)
        if ready:
            text = ready[0].text.strip()
            excerpt = text if len(text) <= 600 else text[:599].rstrip() + "…"

    return NextMeetingReportResponse.from_report(
        report,
        last_summary_excerpt=excerpt,
    )


@router.get(
    "/{patient_id}/meeting-reports",
    response_model=list[MeetingReportListItem],
)
async def list_meeting_reports(
    patient_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    patients: PatientService = Depends(get_patient_service),
    service: NextMeetingReportService = Depends(get_report_service),
) -> list[MeetingReportListItem]:
    await _ensure_patient_exists(current_user.user_id, patient_id, patients)
    reports = await service.list_for_patient(current_user.user_id, patient_id)
    return [MeetingReportListItem.from_report(report) for report in reports]


@router.post(
    "/{patient_id}/meeting-reports/{meeting_id}",
    response_model=NextMeetingReportResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_meeting_report(
    patient_id: uuid.UUID,
    meeting_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    settings: SettingsDep,
    current_user: User = Depends(get_current_user),
    patients: PatientService = Depends(get_patient_service),
    service: NextMeetingReportService = Depends(get_report_service),
) -> NextMeetingReportResponse:
    """Start (or resume) generation of a prep brief for a specific meeting."""
    await _ensure_patient_exists(current_user.user_id, patient_id, patients)
    try:
        await service.verify_meeting_for_patient(current_user.user_id, patient_id, meeting_id)
    except (CalendarEventNotFoundError, MeetingPatientMismatchError) as exc:
        raise _meeting_http_error(exc) from exc

    existing = await service.get(current_user.user_id, meeting_id)
    if existing is not None and existing.status in ("pending", "running"):
        return NextMeetingReportResponse.from_report(existing)

    try:
        report = await service.create_pending(current_user.user_id, patient_id, meeting_id)
    except SQLAlchemyError as exc:
        logger.error("failed to create pending meeting report", exc_info=exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="failed to start meeting report",
        ) from exc

    background_tasks.add_task(
        run_report_generation,
        current_user.user_id,
        patient_id,
        meeting_id,
        settings,
    )
    return NextMeetingReportResponse.from_report(report)


@router.get(
    "/{patient_id}/meeting-reports/{meeting_id}",
    response_model=NextMeetingReportResponse,
)
async def get_meeting_report(
    patient_id: uuid.UUID,
    meeting_id: uuid.UUID,
    response: Response,
    current_user: User = Depends(get_current_user),
    patients: PatientService = Depends(get_patient_service),
    service: NextMeetingReportService = Depends(get_report_service),
    summaries: SummaryRepository = Depends(get_summary_reader),
) -> NextMeetingReportResponse:
    await _ensure_patient_exists(current_user.user_id, patient_id, patients)
    try:
        meeting = await service.verify_meeting_for_patient(
            current_user.user_id,
            patient_id,
            meeting_id,
        )
    except (CalendarEventNotFoundError, MeetingPatientMismatchError) as exc:
        raise _meeting_http_error(exc) from exc

    report = await service.get(current_user.user_id, meeting_id)
    if report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"no meeting report for patient {patient_id} meeting {meeting_id}",
        )

    return await _report_response(
        report,
        user_id=current_user.user_id,
        response=response,
        summaries=summaries,
        before_start_at=meeting.start_at,
    )


@router.post(
    "/{patient_id}/next-meeting-report",
    response_model=NextMeetingReportResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_next_meeting_report(
    patient_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    settings: SettingsDep,
    current_user: User = Depends(get_current_user),
    patients: PatientService = Depends(get_patient_service),
    service: NextMeetingReportService = Depends(get_report_service),
) -> NextMeetingReportResponse:
    """Start (or resume) generation for the patient's current/upcoming meeting."""
    await _ensure_patient_exists(current_user.user_id, patient_id, patients)
    try:
        meeting = await service.resolve_next_meeting(current_user.user_id, patient_id)
    except NoUpcomingMeetingError as exc:
        raise _meeting_http_error(exc) from exc

    return await start_meeting_report(
        patient_id,
        meeting.id,
        background_tasks,
        settings,
        current_user,
        patients,
        service,
    )


@router.get(
    "/{patient_id}/next-meeting-report",
    response_model=NextMeetingReportResponse,
)
async def get_next_meeting_report(
    patient_id: uuid.UUID,
    response: Response,
    current_user: User = Depends(get_current_user),
    patients: PatientService = Depends(get_patient_service),
    service: NextMeetingReportService = Depends(get_report_service),
    summaries: SummaryRepository = Depends(get_summary_reader),
) -> NextMeetingReportResponse:
    """Fetch the prep brief for the patient's current/upcoming meeting."""
    await _ensure_patient_exists(current_user.user_id, patient_id, patients)
    try:
        meeting = await service.resolve_next_meeting(current_user.user_id, patient_id)
    except NoUpcomingMeetingError as exc:
        raise _meeting_http_error(exc) from exc

    return await get_meeting_report(
        patient_id,
        meeting.id,
        response,
        current_user,
        patients,
        service,
        summaries,
    )
