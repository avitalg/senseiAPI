from fastapi import APIRouter, Depends

from analysis.dependencies import get_analysis_service
from analysis.schemas import AnalysisRequest, AnalysisResponse
from analysis.service import AnalysisService

router = APIRouter(prefix="/analysis", tags=["analysis"])


@router.post("", response_model=AnalysisResponse)
async def analyze_transcript(
    body: AnalysisRequest,
    service: AnalysisService = Depends(get_analysis_service),
) -> AnalysisResponse:
    result = await service.analyze(body.transcript)
    return AnalysisResponse.from_result(result)
