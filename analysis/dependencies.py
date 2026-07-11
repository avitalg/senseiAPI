from fastapi import Depends

from analysis.analyzer import Analyzer
from analysis.mock_analyzer import MockAnalyzer
from analysis.service import AnalysisService
from core.config import Settings, get_settings


def get_analyzer(settings: Settings = Depends(get_settings)) -> Analyzer:
    if settings.analyzer_backend == "mock":
        return MockAnalyzer()

    if settings.analyzer_backend == "gemini":
        from analysis.gemini_analyzer import GeminiAnalyzer
        return GeminiAnalyzer(settings.google_api_key, settings.gemini_model)

    raise ValueError(f"Unknown ANALYZER_BACKEND: {settings.analyzer_backend!r}. Expected 'mock' or 'gemini'.")


def get_analysis_service(
    analyzer: Analyzer = Depends(get_analyzer),
) -> AnalysisService:
    return AnalysisService(analyzer)
