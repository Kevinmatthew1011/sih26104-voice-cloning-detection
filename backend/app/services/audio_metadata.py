import hashlib
import io
from dataclasses import dataclass
from typing import Optional
import soundfile as sf


@dataclass
class AudioMetadata:
    """Structured audio container and acoustic metadata."""
    file_hash: str
    sample_rate: Optional[int] = None
    channels: Optional[int] = None
    duration: Optional[float] = None


class AudioMetadataService:
    """
    Extracts acoustic container properties and computes SHA-256 cryptographic fingerprints.
    """

    @staticmethod
    def extract_metadata(content: bytes) -> AudioMetadata:
        """
        Computes SHA-256 integrity fingerprint and attempts safe metadata extraction
        via soundfile header inspection. Falls back gracefully when container headers
        are unparseable or non-standard.
        """
        # 1. Compute SHA-256 integrity fingerprint
        file_hash = hashlib.sha256(content).hexdigest()

        sample_rate: Optional[int] = None
        channels: Optional[int] = None
        duration: Optional[float] = None

        # 2. Inspect audio container properties without decoding entire audio buffer into memory
        if len(content) > 0:
            try:
                from app.ml.audio_decoder import probe_audio_stream
                meta = probe_audio_stream(content)
                sample_rate = meta.get("sample_rate")
                channels = meta.get("channels")
                dur = meta.get("duration")
                duration = round(float(dur), 2) if dur is not None else None
            except Exception:
                # Safe fallback for codecs or headers where decoder cannot inspect metadata
                sample_rate = None
                channels = None
                duration = None

        return AudioMetadata(
            file_hash=file_hash,
            sample_rate=sample_rate,
            channels=channels,
            duration=duration,
        )
