from dataclasses import dataclass


class AnalysisFailedError(Exception):
    """Raised when analysis fails."""


@dataclass(frozen=True)
class AnalysisResult:
    summary: str
    insights: list[str]
    risk_flags: list[str]
