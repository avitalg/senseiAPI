from fastapi import HTTPException, status

from transcription.models import TranscriptionFailedError


def raise_for_transcription_error(exc: Exception) -> None:
    """Map transcription domain errors to HTTP exceptions."""
    if isinstance(exc, TranscriptionFailedError):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
    raise exc
