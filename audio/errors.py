from fastapi import HTTPException, status

from audio.models import (
    AudioNotFoundError,
    AudioTooLargeError,
    EmptyAudioError,
    UnsupportedAudioTypeError,
)


def raise_for_loader_error(exc: Exception) -> None:
    """Map audio-loader domain errors to HTTP exceptions."""
    if isinstance(exc, UnsupportedAudioTypeError):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=str(exc),
        ) from exc
    if isinstance(exc, EmptyAudioError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    if isinstance(exc, AudioTooLargeError):
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=str(exc),
        ) from exc
    if isinstance(exc, AudioNotFoundError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    raise exc
