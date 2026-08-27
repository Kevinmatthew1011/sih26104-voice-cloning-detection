import os
import struct
from pathlib import Path
from typing import Tuple, Optional
from fastapi import UploadFile, HTTPException, status
from app.config import settings


MAGIC_SIGNATURES = {
    b"RIFF": ("audio/wav", ".wav"),
    b"\xff\xfb": ("audio/mpeg", ".mp3"),
    b"\xff\xf3": ("audio/mpeg", ".mp3"),
    b"\xff\xf2": ("audio/mpeg", ".mp3"),
    b"ID3": ("audio/mpeg", ".mp3"),
    b"OggS": ("audio/ogg", ".ogg"),
    b"fLaC": ("audio/flac", ".flac"),
    b"\x1a\x45\xdf\xa3": ("audio/webm", ".webm"),
}


class AudioValidator:
    @staticmethod
    def validate_filename_extension(filename: str) -> str:
        if not filename or "." not in filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Filename is missing or has no extension."
            )
        
        ext = Path(filename).suffix.lower()
        if ext not in settings.ALLOWED_EXTENSIONS:
            allowed = ", ".join(settings.ALLOWED_EXTENSIONS)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported audio extension '{ext}'. Allowed extensions are: {allowed}"
            )
        return ext

    @staticmethod
    async def validate_file_content(file: UploadFile) -> Tuple[bytes, str, int]:
        """
        Validates the audio payload for size, emptiness, and content type.
        Returns: (content_bytes, mime_type, file_size_bytes)
        """
        # Read content
        content = await file.read()
        file_size = len(content)

        # Reset cursor
        await file.seek(0)

        if file_size == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The uploaded audio file is empty (0 bytes)."
            )

        if file_size > settings.MAX_FILE_SIZE_BYTES:
            max_mb = settings.MAX_FILE_SIZE_BYTES / (1024 * 1024)
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File size exceeds maximum permitted limit of {max_mb:.0f}MB."
            )

        # Check MIME type
        content_type = file.content_type or "application/octet-stream"
        
        return content, content_type, file_size

    @staticmethod
    def validate_audio_duration(duration_seconds: Optional[float]) -> None:
        """
        Validates that audio duration does not exceed MAX_AUDIO_DURATION_SECONDS.
        Raises HTTP 400 Bad Request if duration limit is exceeded.
        """
        if duration_seconds is not None and duration_seconds > settings.MAX_AUDIO_DURATION_SECONDS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Audio duration ({duration_seconds:.1f}s) exceeds maximum allowed limit ({settings.MAX_AUDIO_DURATION_SECONDS:.1f}s).",
            )

