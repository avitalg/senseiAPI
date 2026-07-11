from abc import ABC, abstractmethod

from analysis.models import AnalysisResult


class Analyzer(ABC):
    @abstractmethod
    async def analyze(self, transcript: str) -> AnalysisResult: ...
