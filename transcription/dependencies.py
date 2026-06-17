from fastapi import Depends

from core.config import Settings, get_settings
from transcription.transcriber import LocalWhisperTranscriber, Transcriber


def get_transcriber(settings: Settings = Depends(get_settings)) -> Transcriber:
    return LocalWhisperTranscriber(
        model_size=settings.whisper_model,
        device=settings.whisper_device,
        compute_type=settings.whisper_compute_type,
    )
