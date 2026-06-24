from typing import Self

from pydantic import BaseModel

from analysis.models import AnalysisResult


class AnalysisRequest(BaseModel):
    transcript: str


class AnalysisResponse(BaseModel):
    summary: str
    insights: list[str]
    risk_flags: list[str]

    @classmethod
    def from_result(cls, result: AnalysisResult) -> Self:
        return cls(
            summary=result.summary,
            insights=result.insights,
            risk_flags=result.risk_flags,
        )
