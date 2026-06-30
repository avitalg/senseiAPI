from fastapi import APIRouter, Depends

from analysis.dependencies import get_analysis_service
from analysis.errors import raise_for_analysis_error
from analysis.models import AnalysisFailedError
from analysis.schemas import AnalysisRequest, AnalysisResponse
from analysis.service import AnalysisService

router = APIRouter(prefix="/analysis", tags=["analysis"])


@router.post("", response_model=AnalysisResponse)
async def analyze_transcript(
    body: AnalysisRequest,
    service: AnalysisService = Depends(get_analysis_service),
) -> AnalysisResponse:
    try:
        result = await service.analyze(body.transcript)
    except AnalysisFailedError as exc:
        raise_for_analysis_error(exc)
    return AnalysisResponse.from_result(result)
