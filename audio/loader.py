import logging
import uuid
from collections.abc import Iterable, Sequence
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile
from fastapi.concurrency import run_in_threadpool

from audio.models import (
    AudioNotFoundError,
    AudioTooLargeError,
    EmptyAudioError,
    SavedAudio,
    StoredAudioFile,
    UnsupportedAudioTypeError,
)

logger = logging.getLogger(__name__)

_EXTENSION_BY_TYPE = {
    "audio/mpeg": ".mp3",
    "audio/mp3": ".mp3",
    "audio/wav": ".wav",
    "audio/x-wav": ".wav",
    "audio/wave": ".wav",
    "audio/mp4": ".m4a",
    "audio/x-m4a": ".m4a",
    "audio/m4a": ".m4a",
    "audio/aac": ".aac",
    "audio/ogg": ".ogg",
    "audio/flac": ".flac",
    "audio/x-flac": ".flac",
    "audio/webm": ".webm",
}


def _is_safe_audio_id(audio_id: str) -> bool:
    """Reject empty, traversal, or nested ids so lookups stay inside the upload dir."""
    return bool(audio_id) and audio_id not in {".", ".."} and Path(audio_id).name == audio_id


class AudioLoader:
    """Loads, stores, and manages uploaded audio files on the local filesystem."""

    def __init__(
        self,
        *,
        upload_dir: Path,
        max_bytes: int,
        allowed_types: Iterable[str],
    ) -> None:
        self._upload_dir = upload_dir
        self._max_bytes = max_bytes
        self._allowed_types = frozenset(allowed_types)

    async def save(self, user_id: uuid.UUID, file: UploadFile) -> SavedAudio:
        """Validate and persist an uploaded audio file, returning its metadata."""
        content_type = file.content_type or ""
        if content_type not in self._allowed_types:
            raise UnsupportedAudioTypeError(content_type)

        data = await file.read()
        if not data:
            raise EmptyAudioError("uploaded audio file is empty")
        if len(data) > self._max_bytes:
            raise AudioTooLargeError(len(data), self._max_bytes)

        stored_name = f"{uuid4().hex}{self._extension_for(file.filename, content_type)}"
        await run_in_threadpool(
            self._write_file, self._user_upload_dir(user_id) / stored_name, data
        )
        logger.info(
            "stored audio upload",
            extra={"stored_name": stored_name, "size_bytes": len(data)},
        )

        return SavedAudio(
            id=stored_name,
            filename=file.filename or stored_name,
            content_type=content_type,
            size_bytes=len(data),
            data=data,
        )

    async def list_files(self, user_id: uuid.UUID) -> Sequence[StoredAudioFile]:
        return await run_in_threadpool(self._list_sync, user_id)

    async def get_path(self, user_id: uuid.UUID, audio_id: str) -> Path:
        """Return the path to a stored audio file, raising ``AudioNotFoundError`` if missing."""
        return await run_in_threadpool(self._resolve_existing, user_id, audio_id)

    async def read(self, user_id: uuid.UUID, audio_id: str) -> tuple[str, bytes]:
        """Return ``(filename, content)`` for a stored audio file."""
        return await run_in_threadpool(self._read_sync, user_id, audio_id)

    async def delete(self, user_id: uuid.UUID, audio_id: str) -> None:
        await run_in_threadpool(self._delete_sync, user_id, audio_id)

    @staticmethod
    def _extension_for(filename: str | None, content_type: str) -> str:
        if filename:
            suffix = Path(filename).suffix
            if suffix:
                return suffix.lower()
        return _EXTENSION_BY_TYPE.get(content_type, ".bin")

    @staticmethod
    def _write_file(dest: Path, data: bytes) -> None:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)

    def _user_upload_dir(self, user_id: uuid.UUID) -> Path:
        return self._upload_dir / str(user_id)

    def _list_sync(self, user_id: uuid.UUID) -> list[StoredAudioFile]:
        upload_dir = self._user_upload_dir(user_id)
        if not upload_dir.is_dir():
            return []
        return [
            StoredAudioFile(id=path.name, size_bytes=path.stat().st_size)
            for path in sorted(upload_dir.iterdir())
            if path.is_file()
        ]

    def _resolve_existing(self, user_id: uuid.UUID, audio_id: str) -> Path:
        if not _is_safe_audio_id(audio_id):
            raise AudioNotFoundError(audio_id)
        path = self._user_upload_dir(user_id) / audio_id
        if not path.is_file():
            raise AudioNotFoundError(audio_id)
        return path

    def _read_sync(self, user_id: uuid.UUID, audio_id: str) -> tuple[str, bytes]:
        path = self._resolve_existing(user_id, audio_id)
        return path.name, path.read_bytes()

    def _delete_sync(self, user_id: uuid.UUID, audio_id: str) -> None:
        self._resolve_existing(user_id, audio_id).unlink()
