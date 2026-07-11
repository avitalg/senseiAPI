from analysis.analyzer import Analyzer
from analysis.models import AnalysisResult

_MOCK_RESULT = AnalysisResult(
    summary=(
        "The therapist and patient discussed a recent traumatic event. "
        "The patient expressed feelings of hypervigilance and avoidance around familiar locations. "
        "The session focused on grounding techniques and re-establishing a sense of safety."
    ),
    insights=[
        "Patient demonstrates hypervigilance consistent with a trauma response.",
        "Avoidance behaviors are present — patient is avoiding locations"
        " associated with the traumatic event.",
        "Therapist introduced grounding techniques; patient engaged with moderate success.",
        "Therapeutic alliance appears strong; patient was forthcoming and receptive.",
    ],
    risk_flags=[
        "Patient reported disturbed sleep and recurring nightmares over the past week.",
        "Patient expressed feelings of hopelessness regarding recovery progress.",
        "Elevated emotional distress observed during discussion of the traumatic event.",
    ],
)


class MockAnalyzer(Analyzer):
    async def analyze(self, transcript: str) -> AnalysisResult:
        return _MOCK_RESULT
