from fastapi import Depends

from analysis.analyzer import Analyzer, MockAnalyzer
from analysis.service import AnalysisService


def get_analyzer() -> Analyzer:
    return MockAnalyzer()


def get_analysis_service(
    analyzer: Analyzer = Depends(get_analyzer),
) -> AnalysisService:
    return AnalysisService(analyzer)
