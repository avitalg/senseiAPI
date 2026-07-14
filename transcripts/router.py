import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, status

from core.database import SessionDep
from transcripts.schemas import TranscriptExistsResponse
from transcripts.service import TranscriptService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/meetings", tags=["transcripts"])


@router.get(
    "/{meeting_id}/transcript",
    response_model=TranscriptExistsResponse,
)
async def get_meeting_transcript(
    meeting_id: uuid.UUID,
    session: SessionDep,
) -> TranscriptExistsResponse:
    """Lightweight probe — whether a transcript exists for this meeting."""
    transcript = await TranscriptService(session).get_by_meeting_id(meeting_id)
    if transcript is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"no transcript for meeting {meeting_id}",
        )
    return TranscriptExistsResponse.from_transcript(transcript)
