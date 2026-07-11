from core.config import Settings, get_settings
from core.database import SessionDep, SettingsDep
from summaries.repository import SummaryRepository
from summaries.service import SummaryService
from summaries.summarizer import (
    GeminiSummarizer,
    MockSummarizer,
    OllamaSummarizer,
    Summarizer,
)
from transcripts.repository import TranscriptRepository


def get_summarizer(settings: Settings) -> Summarizer:
    """Pick the summarization backend. SDKs are imported lazily so only the selected
    one is ever needed at runtime."""
    if settings.summary_backend == "mock":
        return MockSummarizer()

    if settings.summary_backend == "gemini":
        if not settings.google_api_key:
            raise RuntimeError("GOOGLE_API_KEY must be set when SUMMARY_BACKEND=gemini")
        return GeminiSummarizer(settings.google_api_key, settings.gemini_model)

    from ollama import AsyncClient

    return OllamaSummarizer(
        client=AsyncClient(host=settings.ollama_host, timeout=settings.ollama_timeout_seconds),
        model=settings.ollama_model,
        num_ctx=settings.ollama_num_ctx,
    )


def build_summary_service(session: SessionDep, settings: Settings) -> SummaryService:
    return SummaryService(
        summaries=SummaryRepository(session),
        transcripts=TranscriptRepository(session),
        summarizer=get_summarizer(settings),
        max_transcript_chars=settings.max_transcript_chars,
    )


def get_summary_reader(session: SessionDep) -> SummaryRepository:
    """Reading a summary needs no model, so the read path never constructs one."""
    return SummaryRepository(session)


def get_summary_service(session: SessionDep, settings: SettingsDep) -> SummaryService:
    return build_summary_service(session, settings)


__all__ = [
    "build_summary_service",
    "get_settings",
    "get_summarizer",
    "get_summary_reader",
    "get_summary_service",
]
