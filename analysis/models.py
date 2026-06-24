from dataclasses import dataclass


@dataclass(frozen=True)
class AnalysisResult:
    summary: str
    insights: list[str]
    risk_flags: list[str]
