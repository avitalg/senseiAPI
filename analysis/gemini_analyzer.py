import logging
from pathlib import Path

import httpx
from google import genai
from google.genai import errors as genai_errors
from google.genai import types
from pydantic import BaseModel

from analysis.analyzer import Analyzer
from analysis.models import AnalysisFailedError, AnalysisResult

logger = logging.getLogger(__name__)

_PROMPT_TEMPLATE = (Path(__file__).parent / "analysis_prompt.txt").read_text(encoding="utf-8")


class _AnalysisSchema(BaseModel):
    summary: str
    insights: list[str]
    risk_flags: list[str]


class GeminiAnalyzer(Analyzer):
    def __init__(self, api_key: str, model: str) -> None:
        self._client = genai.Client(api_key=api_key)
        self._model = model

    async def analyze(self, transcript: str) -> AnalysisResult:
        try:
            response = await self._client.aio.models.generate_content(
                model=self._model,
                contents=_PROMPT_TEMPLATE.format(transcript=transcript),
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=_AnalysisSchema,
                ),
            )
        except (genai_errors.APIError, httpx.HTTPError) as exc:
            logger.exception("gemini analysis failed")
            raise AnalysisFailedError("analysis failed") from exc
        parsed: _AnalysisSchema | None = response.parsed
        if parsed is None:
            raise AnalysisFailedError(
                f"Gemini returned an unparseable response. Raw text: {response.text!r}"
            )
        return AnalysisResult(
            summary=parsed.summary,
            insights=parsed.insights,
            risk_flags=parsed.risk_flags,
        )
