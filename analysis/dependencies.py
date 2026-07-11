from fastapi import Depends

from analysis.analyzer import Analyzer
from analysis.mock_analyzer import MockAnalyzer
from analysis.service import AnalysisService
from core.config import get_settings


def get_analyzer() -> Analyzer:
    settings = get_settings()
    backend = settings.analyzer_backend

    if backend == "mock":
        return MockAnalyzer()

    if backend == "gemini":
        from analysis.gemini_analyzer import GeminiAnalyzer
        return GeminiAnalyzer(settings.google_api_key, settings.gemini_model)

    raise ValueError(f"Unknown ANALYZER_BACKEND: {backend!r}. Expected 'mock' or 'gemini'.")


def get_analysis_service(
    analyzer: Analyzer = Depends(get_analyzer),
) -> AnalysisService:
    return AnalysisService(analyzer)
