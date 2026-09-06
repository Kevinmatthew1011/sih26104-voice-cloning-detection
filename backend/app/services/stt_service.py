"""
Speech-to-Text (STT) Service.

Provides robust real-time and batch speech transcription for live call monitoring
and semantic scam-intent evaluation.

Supports:
1. torchaudio Wav2Vec2 ASR (fairseq base 960h CTC acoustic model) for real-time CPU transcription.
2. Explicit unavailable errors; no VAD markers are returned as transcription.
"""

import logging
import re
from pathlib import Path
from typing import Union, Optional, List, Dict, Any
import numpy as np
import torch

from app.ml.audio_decoder import decode_audio
from app.schemas.stt import TranscriptionResponse, WordToken

logger = logging.getLogger(__name__)


class STTUnavailableError(RuntimeError):
    """The local transcription model could not initialize or infer."""


class GreedyCTCDecoder:
    """Greedy CTC decoder for Wav2Vec2 acoustic models."""

    def __init__(self, labels: tuple):
        self.labels = labels
        self.blank = 0

    def decode(self, emission: torch.Tensor) -> str:
        """
        Emission shape: (time_steps, num_classes)
        Collapses repeats and blanks.
        """
        indices = torch.argmax(emission, dim=-1)
        indices = torch.unique_consecutive(indices, dim=-1)
        indices = [i.item() for i in indices if i != self.blank]
        joined = "".join([self.labels[i] for i in indices])
        # Wav2Vec2 uses '|' as word boundary
        return joined.replace("|", " ").strip()


class STTService:
    """
    Unified Speech-to-Text Service.
    """

    _model = None
    _decoder = None
    _bundle = None
    _init_attempted = False

    def __init__(self):
        self._ensure_model_loaded()

    @classmethod
    def _ensure_model_loaded(cls):
        """Lazy load torchaudio Wav2Vec2 ASR model if available."""
        if cls._model is not None or cls._init_attempted:
            return

        cls._init_attempted = True
        try:
            import torchaudio
            bundle = torchaudio.pipelines.WAV2VEC2_ASR_BASE_960H
            # Never download weights in a request. Provision the documented local cache first.
            checkpoint = Path(torch.hub.get_dir()) / "checkpoints" / "wav2vec2_fairseq_base_ls960_asr_ls960.pth"
            if not checkpoint.is_file():
                raise FileNotFoundError(f"Local STT checkpoint missing: {checkpoint}")
            model = bundle.get_model()
            model.eval()
            cls._bundle = bundle
            cls._model = model
            cls._decoder = GreedyCTCDecoder(bundle.get_labels())
            logger.info("Wav2Vec2 ASR pipeline initialized successfully.")
        except Exception as e:
            logger.warning(
                "Wav2Vec2 neural ASR weights not ready or download deferred (%s). "
                "Remote STT is unavailable.",
                e,
            )

    def transcribe(
        self,
        audio_source: Union[str, Path, bytes, np.ndarray],
        sample_rate: int = 16000,
    ) -> TranscriptionResponse:
        """
        Transcribe speech from audio waveform or container bytes.

        Returns a structured TranscriptionResponse DTO.
        """
        if isinstance(audio_source, np.ndarray) and sample_rate != 16000:
            raise ValueError("Array STT input must be 16 kHz mono")
        waveform, sr = decode_audio(audio_source, target_sr=16000, mono=True)
        duration_sec = round(len(waveform) / 16000.0, 3)

        if len(waveform) < 1600:  # < 0.1s
            return TranscriptionResponse(
                text="",
                language="en",
                confidence=0.0,
                duration_seconds=duration_sec,
                engine="empty_buffer",
                tokens=[],
            )

        if duration_sec > 15:
            raise ValueError("STT segments must be at most 15 seconds")

        # 1. Neural Wav2Vec2 inference if available
        if self._model is not None and self._decoder is not None:
            try:
                with torch.no_grad():
                    tensor_waveform = torch.from_numpy(waveform).unsqueeze(0).float()
                    emission, _ = self._model(tensor_waveform)
                    text = self._decoder.decode(emission[0])

                    # Calculate approximate average token confidence from softmax
                    probs = torch.softmax(emission[0], dim=-1)
                    max_probs = torch.max(probs, dim=-1).values
                    conf = float(torch.mean(max_probs).item())

                    # Greedy CTC has no word alignment; do not invent word timestamps.
                    tokens = []

                    return TranscriptionResponse(
                        text=text,
                        language="en",
                        confidence=round(conf, 3),
                        duration_seconds=duration_sec,
                        engine="wav2vec2_asr_base_960h",
                        tokens=tokens,
                    )
            except Exception as e:
                raise STTUnavailableError(f"Local Wav2Vec2 inference failed: {e}") from e

        raise STTUnavailableError("Local Wav2Vec2 checkpoint could not load; no transcription available")


# Global singleton instance
_stt_instance: Optional[STTService] = None


def get_stt_service() -> STTService:
    global _stt_instance
    if _stt_instance is None:
        _stt_instance = STTService()
    return _stt_instance
