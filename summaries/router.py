import logging
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response, status
from sqlalchemy.exc import SQLAlchemyError

from auth.router import get_current_user
from core.database import SessionDep, SettingsDep
from summaries.dependencies import get_summary_reader, get_summary_service
from summaries.repository import SummaryRepository
from summaries.schemas import SummaryResponse
from summaries.service import SummaryService, run_summary_generation
from transcripts.repository import TranscriptRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/meetings", tags=["summaries"])


@router.post(
    "/{meeting_id}/summary",
    response_model=SummaryResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_meeting_summary(
    meeting_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    settings: SettingsDep,
    session: SessionDep,
    service: SummaryService = Depends(get_summary_service),
) -> SummaryResponse:
    """Start (or resume) session-summary generation for a meeting with a transcript."""
    if not settings.summary_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="summary generation is disabled",
        )

    existing = await service.get(meeting_id)
    if existing is not None and existing.status in ("pending", "running"):
        return SummaryResponse.from_summary(existing)

    transcripts = TranscriptRepository(session)
    if await transcripts.get_by_meeting_id(meeting_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"no transcript for meeting {meeting_id}",
        )

    try:
        summary = await service.create_pending(meeting_id)
    except SQLAlchemyError as exc:
        logger.error("failed to create pending summary", exc_info=exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="failed to start summary",
        ) from exc

    background_tasks.add_task(run_summary_generation, meeting_id, settings)
    return SummaryResponse.from_summary(summary)


@router.get("/{meeting_id}/summary", response_model=SummaryResponse)
async def get_meeting_summary(
    meeting_id: uuid.UUID,
    response: Response,
    current_user: User = Depends(get_current_user),
    summaries: SummaryRepository = Depends(get_summary_reader),
) -> SummaryResponse:
    """Fetch the session summary.

    A failed summary is reported with 200 and an ``error``: the request succeeded, and
    it is the summary that failed. The therapist's client renders the reason.

    The summary is a drafting aid the therapist reviews. It is not a clinical record,
    and it must never be relied on to catch a risk disclosure.
    """
    summary = await summaries.get_by_meeting_id(current_user.user_id, meeting_id)
    if summary is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"no summary for meeting {meeting_id}",
        )

    if summary.status in ("pending", "running"):
        response.status_code = status.HTTP_202_ACCEPTED

    return SummaryResponse.from_summary(summary)
