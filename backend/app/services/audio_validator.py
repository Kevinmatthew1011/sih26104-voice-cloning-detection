import io
import os
import struct
import logging
from pathlib import Path
from typing import Tuple, Optional
from fastapi import UploadFile, HTTPException, status
import soundfile as sf
from app.config import settings

logger = logging.getLogger(__name__)


CHUNK_SIZE = 64 * 1024  # 64 KB streaming chunk


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
        Validates the audio payload for size, emptiness, and content type via bounded streaming.
        Aborts immediately when MAX_FILE_SIZE_BYTES is exceeded without buffering oversized payloads.
        Returns: (content_bytes, mime_type, file_size_bytes)
        """
        buffer = bytearray()
        total_read = 0
        max_bytes = settings.MAX_FILE_SIZE_BYTES

        while True:
            chunk = await file.read(CHUNK_SIZE)
            if not chunk:
                break
            total_read += len(chunk)
            if total_read > max_bytes:
                max_mb = max_bytes / (1024 * 1024)
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"File size exceeds maximum permitted limit of {max_mb:.0f}MB."
                )
            buffer.extend(chunk)

        file_size = len(buffer)
        content_bytes = bytes(buffer)

        # Reset file cursor
        await file.seek(0)

        if file_size == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The uploaded audio file is empty (0 bytes)."
            )

        content_type = file.content_type or "application/octet-stream"
        return content_bytes, content_type, file_size

    @staticmethod
    def validate_format_plausibility(content: bytes, ext: str) -> None:
        """
        Verifies format-aware container signatures for allowed extensions.
        Rejects mismatched or arbitrary binary payloads disguised with valid extensions.
        """
        if len(content) < 4:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Audio file header is too short or malformed."
            )

        ext = ext.lower()
        valid = False

        if ext == ".wav":
            # RIFF....WAVE
            valid = content[:4] == b"RIFF" and len(content) >= 12 and content[8:12] == b"WAVE"
        elif ext == ".flac":
            # fLaC
            valid = content[:4] == b"fLaC"
        elif ext == ".ogg":
            # OggS
            valid = content[:4] == b"OggS"
        elif ext == ".webm":
            # WebM / Matroska EBML Document ID (\x1a\x45\xdf\xa3) at offset 0
            valid = content[:4] == b"\x1a\x45\xdf\xa3"
        elif ext == ".mp3":
            # ID3 tag or MPEG audio sync frame (0xFFE0 mask)
            if content[:3] == b"ID3":
                valid = True
            elif len(content) >= 2 and content[0] == 0xFF and (content[1] & 0xE0) == 0xE0:
                valid = True
        elif ext in [".m4a", ".mp4"]:
            # ftyp box at offset 4 or within initial 32 bytes
            valid = (len(content) >= 8 and content[4:8] == b"ftyp") or (b"ftyp" in content[:32])
        elif ext == ".aac":
            # ADTS sync (0xFFF1 / 0xFFF9) or ADIF or ftyp
            if len(content) >= 2 and content[:2] in (b"\xff\xf1", b"\xff\xf9"):
                valid = True
            elif content[:4] == b"ADIF":
                valid = True
            elif len(content) >= 8 and content[4:8] == b"ftyp":
                valid = True
        else:
            # Fallback for other configured extensions
            valid = True

        if not valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File content does not match declared audio format '{ext}'. Corrupt or invalid container header."
            )

    @staticmethod
    def probe_audio_decodability(content: bytes, ext: str = ".wav") -> None:
        """
        Attempts a safe decoder inspection of the audio payload.
        Ensures that syntactically plausible headers also contain parseable audio streams.
        """
        from app.ml.audio_decoder import probe_audio_stream
        try:
            probe_audio_stream(content, ext)
        except Exception as e:
            logger.warning(f"Audio decodability probe failed for format '{ext}': {e}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Audio file could not be decoded. File is corrupt or in an unparseable format."
            )

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

