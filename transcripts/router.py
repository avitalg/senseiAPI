"""Meeting transcript probe + delete (clears slate for re-upload)."""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, status

from auth.router import get_current_user
from auth.schemas import User
from core.database import SessionDep
from summaries.repository import SummaryRepository
from transcripts.repository import TranscriptRepository
from transcripts.schemas import MeetingTranscriptOut

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/meetings", tags=["transcripts"])


@router.get("/{meeting_id}/transcript", response_model=MeetingTranscriptOut)
async def get_meeting_transcript(
    meeting_id: uuid.UUID,
    session: SessionDep,
    current_user: User = Depends(get_current_user),
) -> MeetingTranscriptOut:
    """Probe whether a meeting already has a stored transcript (upload conflict check)."""
    transcripts = TranscriptRepository(session)
    stored = await transcripts.get_by_meeting_id(current_user.user_id, meeting_id)
    if stored is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"no transcript for meeting {meeting_id}",
        )
    return MeetingTranscriptOut.from_stored(stored)


@router.delete("/{meeting_id}/transcript", status_code=status.HTTP_204_NO_CONTENT)
async def delete_meeting_transcript(
    meeting_id: uuid.UUID,
    session: SessionDep,
    current_user: User = Depends(get_current_user),
) -> None:
    """Delete the meeting transcript and its summary so audio can be uploaded again.

    Summary is removed in the same call: a dangling summary without a transcript
    would block a clean re-upload flow and confuse the Summary page.
    """
    transcripts = TranscriptRepository(session)
    summaries = SummaryRepository(session)
    deleted_transcript = await transcripts.delete_by_meeting_id(current_user.user_id, meeting_id)
    deleted_summary = await summaries.delete_by_meeting_id(current_user.user_id, meeting_id)
    if not deleted_transcript and not deleted_summary:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"no transcript or summary for meeting {meeting_id}",
        )
