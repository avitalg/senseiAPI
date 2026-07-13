import logging
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response, status
from sqlalchemy.exc import SQLAlchemyError

from core.database import SettingsDep
from patients.dependencies import get_patient_service
from patients.models import PatientNotFoundError
from patients.service import PatientService
from reports.dependencies import get_report_reader, get_report_service
from reports.repository import NextMeetingReportRepository
from reports.schemas import NextMeetingReportResponse
from reports.service import NextMeetingReportService, run_report_generation
from summaries.dependencies import get_summary_reader
from summaries.repository import SummaryRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/patients", tags=["next-meeting-reports"])


@router.post(
    "/{patient_id}/next-meeting-report",
    response_model=NextMeetingReportResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_next_meeting_report(
    patient_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    settings: SettingsDep,
    patients: PatientService = Depends(get_patient_service),
    service: NextMeetingReportService = Depends(get_report_service),
) -> NextMeetingReportResponse:
    """Start (or resume) generation of the patient's cross-meeting prep brief."""
    try:
        await patients.get_patient(patient_id)
    except PatientNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except SQLAlchemyError as exc:
        logger.error("failed to load patient for next-meeting report", exc_info=exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="failed to start next-meeting report",
        ) from exc

    existing = await service.get(patient_id)
    if existing is not None and existing.status in ("pending", "running"):
        return NextMeetingReportResponse.from_report(existing)

    try:
        report = await service.create_pending(patient_id)
    except SQLAlchemyError as exc:
        logger.error("failed to create pending next-meeting report", exc_info=exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="failed to start next-meeting report",
        ) from exc

    background_tasks.add_task(run_report_generation, patient_id, settings)
    return NextMeetingReportResponse.from_report(report)


@router.get(
    "/{patient_id}/next-meeting-report",
    response_model=NextMeetingReportResponse,
)
async def get_next_meeting_report(
    patient_id: uuid.UUID,
    response: Response,
    reports: NextMeetingReportRepository = Depends(get_report_reader),
    summaries: SummaryRepository = Depends(get_summary_reader),
) -> NextMeetingReportResponse:
    report = await reports.get_by_patient_id(patient_id)
    if report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"no next-meeting report for patient {patient_id}",
        )

    if report.status in ("pending", "running"):
        response.status_code = status.HTTP_202_ACCEPTED
        return NextMeetingReportResponse.from_report(report)

    excerpt = None
    if report.status == "ready":
        ready = await summaries.list_ready_for_patient(patient_id, limit=1)
        if ready:
            text = ready[0].text.strip()
            excerpt = text if len(text) <= 600 else text[:599].rstrip() + "…"

    return NextMeetingReportResponse.from_report(
        report,
        last_summary_excerpt=excerpt,
    )
