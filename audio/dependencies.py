from fastapi import Depends

from audio.loader import AudioLoader
from audio.service import AudioService
from core.config import Settings, get_settings
from transcription.dependencies import get_transcriber
from transcription.transcriber import Transcriber


def get_audio_loader(settings: Settings = Depends(get_settings)) -> AudioLoader:
    return AudioLoader(
        upload_dir=settings.upload_dir,
        max_bytes=settings.max_upload_bytes,
        allowed_types=settings.allowed_audio_types,
    )


def get_audio_service(
    loader: AudioLoader = Depends(get_audio_loader),
    transcriber: Transcriber = Depends(get_transcriber),
    settings: Settings = Depends(get_settings),
) -> AudioService:
    return AudioService(loader, transcriber, language=settings.transcribe_language)
