import logging
from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from typing import Any, Protocol

from summaries.format import normalize_summary_output
from summaries.models import Summary, SummaryFailedError
from summaries.prompt import THERAPIST_SUMMARY_SYSTEM_PROMPT

logger = logging.getLogger(__name__)


class OllamaClient(Protocol):
    async def chat(
        self,
        model: str,
        messages: Sequence[Mapping[str, str]],
        *,
        options: Mapping[str, int],
    ) -> Any: ...


class OpenAIChatCompletions(Protocol):
    """Slice of ``AsyncOpenAI.chat.completions`` used for summarization."""

    async def create(self, **kwargs: Any) -> Any: ...


class OpenAIClient(Protocol):
    """Structural type for the OpenAI SDK chat client (property or attribute)."""

    @property
    def chat(self) -> Any: ...


class Summarizer(ABC):
    """Turns a transcript into a session summary."""

    @abstractmethod
    async def summarize(self, *, text: str, language: str) -> Summary: ...


class OllamaSummarizer(Summarizer):
    """Summarization by a local model served by Ollama."""

    def __init__(self, *, client: OllamaClient, model: str, num_ctx: int) -> None:
        self._client = client
        self._model = model
        self._num_ctx = num_ctx

    async def summarize(self, *, text: str, language: str) -> Summary:
        try:
            response = await self._client.chat(
                model=self._model,
                messages=[
                    {"role": "system", "content": THERAPIST_SUMMARY_SYSTEM_PROMPT},
                    {"role": "user", "content": text},
                ],
                # Ollama defaults num_ctx to 2048 and silently truncates anything longer,
                # which would summarise the opening minutes of a session and say nothing.
                options={"num_ctx": self._num_ctx},
            )
        except Exception as exc:
            logger.error("ollama summarization failed", exc_info=exc)
            raise SummaryFailedError(f"summarization failed: {exc}") from exc

        summary_text = normalize_summary_output(response["message"]["content"])
        if not summary_text:
            raise SummaryFailedError("the model returned an empty summary")
        return Summary(text=summary_text, model=self._model)


class OpenAISummarizer(Summarizer):
    """Summarization via the hosted OpenAI Chat Completions API.

    Transcripts leave the host — use only when SUMMARY_BACKEND=openai is intentional.
    """

    def __init__(self, *, client: OpenAIClient, model: str) -> None:
        self._client = client
        self._model = model

    async def summarize(self, *, text: str, language: str) -> Summary:
        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": THERAPIST_SUMMARY_SYSTEM_PROMPT},
                    {"role": "user", "content": text},
                ],
                temperature=0,
            )
        except Exception as exc:
            logger.error("openai summarization failed", exc_info=exc)
            raise SummaryFailedError(f"summarization failed: {exc}") from exc

        try:
            content = response.choices[0].message.content or ""
        except (AttributeError, IndexError, TypeError) as exc:
            raise SummaryFailedError("the model returned an empty summary") from exc

        summary_text = normalize_summary_output(content)
        if not summary_text:
            raise SummaryFailedError("the model returned an empty summary")
        return Summary(text=summary_text, model=self._model)
