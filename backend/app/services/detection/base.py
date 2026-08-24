from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, Dict, Any
from app.schemas.detection import DetectionResultDTO


class BaseDetectionService(ABC):
    """
    Abstract Base Class defining the AI/ML Voice Cloning Detection Service Interface.
    
    Any future real AI/ML model (e.g. Wav2Vec2, RawNet2, Whisper features + classifier,
    diffusion anomaly detector) MUST inherit from this class and implement the `detect`
    and `get_model_info` methods.
    
    This ensures zero-friction substitution of the mock model with teammate's real model.
    """

    @abstractmethod
    async def detect(
        self,
        audio_path: Path,
        filename: str,
        mime_type: str,
        file_size_bytes: int,
        duration_seconds: Optional[float] = None,
        extra_metadata: Optional[Dict[str, Any]] = None,
    ) -> DetectionResultDTO:
        """
        Analyze the audio file and return a structured DetectionResultDTO.
        
        Args:
            audio_path: Path to the validated audio file on disk.
            filename: Original uploaded filename.
            mime_type: Detected or declared MIME type.
            file_size_bytes: Total size of the audio in bytes.
            duration_seconds: Estimated or exact audio duration in seconds.
            extra_metadata: Optional dict for supplementary telemetry.

        Returns:
            DetectionResultDTO containing prediction, confidence, risk_level,
            model_version, processing_time_ms, and forensic details.
        """
        pass

    @abstractmethod
    def get_model_info(self) -> Dict[str, Any]:
        """
        Return metadata regarding the current active model (version, architecture, capabilities).
        """
        pass
