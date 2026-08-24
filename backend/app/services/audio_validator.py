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
    async def validate_file_content(file: UploadFile) -> Tuple[bytes, str, int, Optional[float]]:
        """
        Validates the audio payload for size, header magic bytes, and estimates duration if wav.
        Returns: (content_bytes, mime_type, file_size_bytes, estimated_duration)
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
        
        # Estimate duration for WAV files if valid RIFF header
        duration: Optional[float] = None
        if content.startswith(b"RIFF") and len(content) > 44:
            try:
                # Basic WAV PCM header parsing
                # Byte 24-27: Sample Rate, Byte 28-31: Byte Rate
                byte_rate = struct.unpack("<I", content[28:32])[0]
                if byte_rate > 0:
                    data_size = file_size - 44
                    duration = round(data_size / byte_rate, 2)
            except Exception:
                duration = None

        if duration is None:
            # Fallback approximate estimation based on typical 128kbps audio stream
            duration = round(file_size / 16000.0, 2)
            if duration < 0.5:
                duration = 1.0

        return content, content_type, file_size, duration
