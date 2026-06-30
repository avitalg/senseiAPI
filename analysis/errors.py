from fastapi import HTTPException, status

from analysis.models import AnalysisFailedError


def raise_for_analysis_error(exc: Exception) -> None:
    """Map analysis domain errors to HTTP exceptions."""
    if isinstance(exc, AnalysisFailedError):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Transcript analysis failed.",
        ) from exc
    raise exc
