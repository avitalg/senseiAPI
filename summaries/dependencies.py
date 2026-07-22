from core.config import Settings, get_settings
from core.database import SessionDep, SettingsDep
from summaries.repository import SummaryRepository
from summaries.service import SummaryService
from summaries.summarizer import OllamaSummarizer, OpenAISummarizer, Summarizer
from transcripts.repository import TranscriptRepository


def get_summarizer(settings: Settings) -> Summarizer:
    """Build the configured summarizer (Ollama local or OpenAI hosted)."""
    if settings.summary_backend == "openai":
        if not settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is required when SUMMARY_BACKEND=openai")
        # Imported lazily so the SDK is only needed when this backend is selected.
        from openai import AsyncOpenAI

        return OpenAISummarizer(
            client=AsyncOpenAI(
                api_key=settings.openai_api_key,
                base_url=settings.openai_base_url,
            ),
            model=settings.openai_model,
        )

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
