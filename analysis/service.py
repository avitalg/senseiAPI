from analysis.analyzer import Analyzer
from analysis.models import AnalysisResult


class AnalysisService:
    def __init__(self, analyzer: Analyzer) -> None:
        self._analyzer = analyzer

    async def analyze(self, transcript: str) -> AnalysisResult:
        return await self._analyzer.analyze(transcript)
