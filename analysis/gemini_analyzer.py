from google import genai
from google.genai import types
from pydantic import BaseModel

from analysis.analyzer import Analyzer
from analysis.models import AnalysisResult

_MODEL = "gemini-2.5-flash"

_PROMPT_TEMPLATE = """\
You are a clinical AI assistant. Analyze the following therapy session transcript \
and return a structured JSON object written entirely in Hebrew.

Guidelines:
- Base the analysis strictly on what is said in the transcript. Do not infer beyond it.
- Do not provide medical diagnoses or express clinical certainty.

Field definitions:
- summary: A short, factual overview of the session (2–3 sentences).
- insights: Key therapeutic observations from the session — emotional themes, \
behavioral patterns, coping strategies, strengths, or recurring dynamics \
that emerged in the conversation.
- risk_flags: Clinically meaningful concerns that may require the therapist's \
additional assessment, monitoring, follow-up, or intervention. \
Do not repeat observations already listed in insights. \
If no such concerns are present, return an empty list.

Transcript:
{transcript}
"""


class _AnalysisSchema(BaseModel):
    summary: str
    insights: list[str]
    risk_flags: list[str]


class GeminiAnalyzer(Analyzer):
    def __init__(self, api_key: str) -> None:
        self._client = genai.Client(api_key=api_key)

    async def analyze(self, transcript: str) -> AnalysisResult:
        response = await self._client.aio.models.generate_content(
            model=_MODEL,
            contents=_PROMPT_TEMPLATE.format(transcript=transcript),
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=_AnalysisSchema,
            ),
        )
        parsed: _AnalysisSchema | None = response.parsed
        if parsed is None:
            raise ValueError(
                f"Gemini returned an unparseable response. Raw text: {response.text!r}"
            )
        return AnalysisResult(
            summary=parsed.summary,
            insights=parsed.insights,
            risk_flags=parsed.risk_flags,
        )
