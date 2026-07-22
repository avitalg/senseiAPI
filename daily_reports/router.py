import logging
import uuid
from datetime import date, datetime
from typing import Annotated
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Response, status
from sqlalchemy.exc import SQLAlchemyError

from auth.router import get_current_user
from auth.schemas import User
from core.database import SettingsDep
from daily_reports.dependencies import get_daily_report_service
from daily_reports.schemas import (
    DEFAULT_DAILY_MEETING_LIMIT,
    DEFAULT_DAILY_TIME_ZONE,
    MAX_DAILY_MEETING_LIMIT,
    DailyMeetingReportResponse,
)
from daily_reports.service import DailyMeetingReportService, run_daily_report_generation
from tts.dependencies import build_tts_service
from tts.errors import (
    EmptyTextError,
    InvalidSpeechSpeedError,
    SpeechSynthesisFailedError,
    TextTooLongError,
    TTSConfigurationError,
)
from tts.models import MAX_SPEECH_SPEED, MIN_SPEECH_SPEED

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/daily-meeting-reports", tags=["daily-meeting-reports"])


def _time_zone(value: str) -> ZoneInfo:
    try:
        return ZoneInfo(value)
    except ZoneInfoNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="invalid time_zone",
        ) from exc


def _set_report_status(response: Response, status_value: str) -> None:
    if status_value in ("pending", "running"):
        response.status_code = status.HTTP_202_ACCEPTED
    else:
        response.status_code = status.HTTP_200_OK


def _speech_http_error(exc: Exception) -> HTTPException:
    if isinstance(
        exc,
        (EmptyTextError, TextTooLongError, InvalidSpeechSpeedError),
    ):
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        )
    return HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail="failed to synthesize speech",
    )


@router.post(
    "",
    response_model=DailyMeetingReportResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_daily_meeting_report(
    background_tasks: BackgroundTasks,
    response: Response,
    settings: SettingsDep,
    report_date: Annotated[date | None, Query()] = None,
    time_zone: Annotated[str, Query(min_length=1, max_length=64)] = DEFAULT_DAILY_TIME_ZONE,
    meeting_limit: Annotated[
        int,
        Query(ge=1, le=MAX_DAILY_MEETING_LIMIT),
    ] = DEFAULT_DAILY_MEETING_LIMIT,
    refresh: Annotated[bool, Query()] = False,
    current_user: User = Depends(get_current_user),
    service: DailyMeetingReportService = Depends(get_daily_report_service),
) -> DailyMeetingReportResponse:
    zone = _time_zone(time_zone)
    resolved_date = report_date or datetime.now(zone).date()
    try:
        report, should_generate = await service.request_report(
            current_user.user_id,
            resolved_date,
            time_zone=zone.key,
            meeting_limit=meeting_limit,
            refresh=refresh,
        )
    except SQLAlchemyError as exc:
        logger.error("failed to request daily meeting report", exc_info=exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="failed to start daily meeting report",
        ) from exc

    if should_generate:
        background_tasks.add_task(
            run_daily_report_generation,
            current_user.user_id,
            report.id,
            settings,
        )
    _set_report_status(response, report.status)
    return DailyMeetingReportResponse.from_report(report)


@router.get("/{report_id}", response_model=DailyMeetingReportResponse)
async def get_daily_meeting_report(
    report_id: uuid.UUID,
    response: Response,
    current_user: User = Depends(get_current_user),
    service: DailyMeetingReportService = Depends(get_daily_report_service),
) -> DailyMeetingReportResponse:
    try:
        report = await service.get(current_user.user_id, report_id)
    except SQLAlchemyError as exc:
        logger.error("failed to get daily meeting report", exc_info=exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="failed to get daily meeting report",
        ) from exc
    if report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="daily meeting report not found",
        )
    _set_report_status(response, report.status)
    return DailyMeetingReportResponse.from_report(report)


@router.get("/{report_id}/speech")
async def get_daily_meeting_report_speech(
    report_id: uuid.UUID,
    settings: SettingsDep,
    speed: Annotated[
        float,
        Query(ge=MIN_SPEECH_SPEED, le=MAX_SPEECH_SPEED),
    ] = 1.0,
    current_user: User = Depends(get_current_user),
    service: DailyMeetingReportService = Depends(get_daily_report_service),
) -> Response:
    try:
        report = await service.get(current_user.user_id, report_id)
    except SQLAlchemyError as exc:
        logger.error("failed to get daily meeting report for speech", exc_info=exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="failed to get daily meeting report",
        ) from exc
    if report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="daily meeting report not found",
        )
    if report.status in ("pending", "running"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="daily meeting report is still generating",
        )
    if report.status == "failed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=report.error or "daily meeting report generation failed",
        )

    try:
        tts_service = build_tts_service(settings)
    except TTSConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="text-to-speech is not available",
        ) from exc

    try:
        audio = await tts_service.synthesize(
            text=report.text or "",
            speed=speed,
        )
    except (
        EmptyTextError,
        TextTooLongError,
        InvalidSpeechSpeedError,
        SpeechSynthesisFailedError,
    ) as exc:
        raise _speech_http_error(exc) from exc

    return Response(content=audio.data, media_type=audio.media_type)
