import mimetypes

from fastapi import APIRouter, Depends, File, UploadFile, status
from fastapi.responses import FileResponse

from audio.dependencies import get_audio_service
from audio.errors import raise_for_loader_error
from audio.models import (
    AudioNotFoundError,
    AudioTooLargeError,
    EmptyAudioError,
    UnsupportedAudioTypeError,
)
from audio.schemas import AudioFileInfo, AudioUploadResponse
from audio.service import AudioService
from transcription.errors import raise_for_transcription_error
from transcription.models import TranscriptionFailedError
from transcription.schemas import TranscriptionResponse

router = APIRouter(prefix="/audio", tags=["audio"])


@router.post("/upload", response_model=AudioUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_audio(
    file: UploadFile = File(...),
    service: AudioService = Depends(get_audio_service),
) -> AudioUploadResponse:
    try:
        saved, transcript = await service.upload_and_transcribe(file)
    except (
        UnsupportedAudioTypeError,
        EmptyAudioError,
        AudioTooLargeError,
    ) as exc:
        raise_for_loader_error(exc)
    except TranscriptionFailedError as exc:
        raise_for_transcription_error(exc)
    return AudioUploadResponse.from_upload(saved, transcript)


@router.get("", response_model=list[AudioFileInfo])
async def list_audio_files(
    service: AudioService = Depends(get_audio_service),
) -> list[AudioFileInfo]:
    files = await service.list_files()
    return [AudioFileInfo.from_stored(file) for file in files]


@router.get("/{audio_id}", response_class=FileResponse)
async def download_audio(
    audio_id: str,
    service: AudioService = Depends(get_audio_service),
) -> FileResponse:
    try:
        path = await service.get_path(audio_id)
    except AudioNotFoundError as exc:
        raise_for_loader_error(exc)
    media_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    return FileResponse(path, media_type=media_type, filename=path.name)


@router.delete("/{audio_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_audio(
    audio_id: str,
    service: AudioService = Depends(get_audio_service),
) -> None:
    try:
        await service.delete(audio_id)
    except AudioNotFoundError as exc:
        raise_for_loader_error(exc)


@router.post("/{audio_id}/transcribe", response_model=TranscriptionResponse)
async def transcribe_audio(
    audio_id: str,
    service: AudioService = Depends(get_audio_service),
) -> TranscriptionResponse:
    try:
        transcript = await service.transcribe(audio_id)
    except AudioNotFoundError as exc:
        raise_for_loader_error(exc)
    except TranscriptionFailedError as exc:
        raise_for_transcription_error(exc)
    return TranscriptionResponse.from_transcript(audio_id, transcript)
