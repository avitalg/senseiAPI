"""Provider-independent text-to-speech support for internal application code."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tts.models import AudioFormat, SynthesizedAudio

if TYPE_CHECKING:
    from core.config import Settings


async def text_to_speech(
    text: str,
    *,
    language: str | None = None,
    voice: str | None = None,
    speed: float | None = None,
    output_format: AudioFormat | None = None,
    settings: Settings | None = None,
) -> SynthesizedAudio:
    """Synthesize text with application defaults and return in-memory audio."""
    # Local imports keep core.config -> tts.models free of an import cycle.
    from core.config import get_settings
    from tts.dependencies import build_tts_service

    resolved_settings = get_settings() if settings is None else settings
    service = build_tts_service(resolved_settings)
    return await service.synthesize(
        text=text,
        language=language,
        voice=voice,
        speed=speed,
        output_format=output_format,
    )


__all__ = ["SynthesizedAudio", "text_to_speech"]
