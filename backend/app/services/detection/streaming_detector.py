"""
Streaming Sliding-Window Audio Detector for Real-Time Call Monitoring.

Implements real-time sliding-window acoustic spoof detection on streaming audio:
- Standard 64,600-sample (~4.0375s at 16 kHz) AASIST temporal window.
- 16,150-sample (~1.009375s, 75% overlap) sliding window hop.
- Buffer safety limits (300.0s max duration).
- Decoupled detection engine invocation (AASIST, baseline, or mock).
- Zero fake probabilities or simulated progress.
"""

import io
import logging
from typing import List, Dict, Any, Optional
import numpy as np

from app.config import settings
from app.services.detection.factory import get_detection_service
from app.services.detection.aasist_service import AASISTDetectionService
from app.ml.audio_decoder import decode_audio

logger = logging.getLogger("app.detections.streaming")

TARGET_SAMPLE_RATE: int = 16000
TARGET_WINDOW_SAMPLES: int = 64600  # ~4.0375 seconds @ 16 kHz
TARGET_HOP_SAMPLES: int = 16150     # ~1.009375 seconds (75% overlap)
MAX_BUFFER_SAMPLES: int = 300 * TARGET_SAMPLE_RATE  # 5.0 minutes (4,800,000 samples)


class StreamingAASISTDetector:
    """
    Stateful streaming audio detector for a single WebSocket monitoring session.
    Buffers incoming audio chunks, segments into 75% overlapping sliding windows,
    and returns live acoustic detection updates.
    """

    def __init__(self, engine_type: Optional[str] = None):
        self.engine_type = (engine_type or settings.DETECTION_ENGINE).strip().lower()
        self.window_length = TARGET_WINDOW_SAMPLES
        self.hop_length = TARGET_HOP_SAMPLES
        self.sample_rate = TARGET_SAMPLE_RATE

        # In-memory float32 16 kHz PCM buffer
        self.pcm_buffer: np.ndarray = np.zeros(0, dtype=np.float32)
        # Byte accumulator for containerized formats (e.g. WebM, OGG)
        self.raw_bytes_buffer: bytearray = bytearray()

        self.next_window_start: int = 0
        self.window_index: int = 0
        self.analyzed_windows: List[Dict[str, Any]] = []
        self._is_cleaned_up: bool = False

    def decode_and_append_chunk(
        self,
        chunk: bytes,
        specified_format: Optional[str] = None,
    ) -> None:
        """
        Decode an incoming binary audio chunk and append its float32 16 kHz samples to pcm_buffer.
        Supports:
        - raw PCM16: 16-bit signed integer linear PCM @ 16 kHz mono
        - raw PCM_F32: 32-bit float linear PCM @ 16 kHz mono
        - WAV container (RIFF header)
        - WebM / OGG container (streaming MediaRecorder chunks)
        """
        if not chunk or len(chunk) == 0:
            return

        fmt = (specified_format or "").strip().lower()

        # 1. Explicit or auto-detected PCM16
        if fmt == "pcm16":
            if len(chunk) % 2 != 0:
                raise ValueError(
                    f"Invalid PCM16 chunk length ({len(chunk)} bytes): payload length must be a multiple of 2 bytes."
                )
            new_samples = np.frombuffer(chunk, dtype=np.int16).astype(np.float32) / 32768.0
            self.pcm_buffer = np.concatenate([self.pcm_buffer, new_samples])
            return

        # 2. Explicit PCM Float32
        if fmt == "pcm_f32":
            if len(chunk) % 4 != 0:
                raise ValueError(
                    f"Invalid PCM float32 chunk length ({len(chunk)} bytes): payload length must be a multiple of 4 bytes."
                )
            new_samples = np.frombuffer(chunk, dtype=np.float32)
            self.pcm_buffer = np.concatenate([self.pcm_buffer, new_samples])
            return

        # 3. Explicit or auto-detected WAV (starts with 'RIFF')
        if fmt == "wav" or chunk.startswith(b"RIFF"):
            try:
                samples, _ = decode_audio(chunk, target_sr=self.sample_rate, mono=True)
                self.pcm_buffer = np.concatenate([self.pcm_buffer, samples])
                return
            except Exception as e:
                raise ValueError(f"Failed to decode WAV chunk: {e}") from e

        # 4. WebM / OGG container streaming (accumulated in byte buffer)
        is_webm = chunk.startswith(b"\x1a\x45\xdf\xa3") or self.raw_bytes_buffer.startswith(b"\x1a\x45\xdf\xa3")
        is_ogg = chunk.startswith(b"OggS") or self.raw_bytes_buffer.startswith(b"OggS")

        if fmt in ("webm", "ogg") or is_webm or is_ogg:
            self.raw_bytes_buffer.extend(chunk)
            try:
                samples, _ = decode_audio(bytes(self.raw_bytes_buffer), target_sr=self.sample_rate, mono=True)
                self.pcm_buffer = samples
                return
            except Exception as e:
                # If incomplete frame at end of stream, wait for subsequent chunk unless buffer is corrupted
                if len(self.raw_bytes_buffer) > 1024 * 1024 and len(self.pcm_buffer) == 0:
                    raise ValueError(f"Could not decode containerized audio stream: {e}") from e
                return

        # 5. Default fallback: treat as raw PCM16 if payload length is even
        if len(chunk) % 2 == 0:
            new_samples = np.frombuffer(chunk, dtype=np.int16).astype(np.float32) / 32768.0
            self.pcm_buffer = np.concatenate([self.pcm_buffer, new_samples])
            return

        raise ValueError(
            f"Unsupported or corrupt audio payload format ({len(chunk)} bytes). "
            "Expected 16 kHz 16-bit PCM, WAV, WebM, or Ogg container."
        )

    def predict_window(self, waveform: np.ndarray) -> Dict[str, Any]:
        """
        Execute window inference on the current sliding window using the configured detection engine.
        """
        if self.engine_type == "aasist":
            # Real AASIST inference
            aasist_service = AASISTDetectionService(model_version="aasist-v1")
            return aasist_service.predict_window(waveform)

        # Fallback to factory service (e.g. mock or baseline)
        service = get_detection_service()
        if hasattr(service, "predict_window"):
            return service.predict_window(waveform)

        raise NotImplementedError(
            f"Active detection service '{self.engine_type}' does not implement predict_window"
        )

    def process_chunk(
        self,
        chunk: bytes,
        specified_format: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Process an incoming audio chunk and return any newly triggered events
        (status buffering or acoustic_update events).
        """
        self.decode_and_append_chunk(chunk, specified_format=specified_format)

        if len(self.pcm_buffer) > MAX_BUFFER_SAMPLES:
            raise ValueError(
                f"Audio stream duration ({len(self.pcm_buffer) / self.sample_rate:.1f}s) "
                f"exceeds maximum allowed limit of {MAX_BUFFER_SAMPLES / self.sample_rate:.0f}s."
            )

        events: List[Dict[str, Any]] = []

        # Sliding window loop: advance by hop_length for each full window available
        while len(self.pcm_buffer) >= self.next_window_start + self.window_length:
            window_slice = self.pcm_buffer[
                self.next_window_start : self.next_window_start + self.window_length
            ]
            start_sec = round(self.next_window_start / self.sample_rate, 4)
            end_sec = round((self.next_window_start + self.window_length) / self.sample_rate, 4)

            # Run inference
            result = self.predict_window(window_slice)

            update_event = {
                "type": "acoustic_update",
                "window_index": self.window_index,
                "start_seconds": start_sec,
                "end_seconds": end_sec,
                "synthetic_probability": result["synthetic_probability"],
                "prediction": result["prediction"],
                "risk_level": result["risk_level"],
                "action": result["action"],
                "model_version": result.get("model_version", "aasist-v1"),
                "confidence": result.get("confidence", result["synthetic_probability"]),
                "cm_score": result.get("cm_score"),
                "cumulative_windows": self.window_index + 1,
            }

            self.analyzed_windows.append(update_event)
            events.append(update_event)

            self.next_window_start += self.hop_length
            self.window_index += 1

        # If no new windows were ready, emit buffering status
        if not events:
            events.append(self.get_buffering_status())

        return events

    def get_buffering_status(self) -> Dict[str, Any]:
        """Current buffering state telemetry."""
        buffered_sec = round(len(self.pcm_buffer) / self.sample_rate, 3)
        req_sec = round((self.next_window_start + self.window_length) / self.sample_rate, 3)
        return {
            "type": "status",
            "state": "buffering",
            "buffered_seconds": buffered_sec,
            "required_seconds": req_sec,
            "samples_buffered": len(self.pcm_buffer),
            "samples_required": self.next_window_start + self.window_length,
            "windows_analyzed": self.window_index,
        }

    def get_session_summary(self) -> Dict[str, Any]:
        """Comprehensive session summary upon call termination."""
        valid_probs = [
            w["synthetic_probability"]
            for w in self.analyzed_windows
            if w.get("synthetic_probability") is not None
        ]
        peak_synth = max(valid_probs) if valid_probs else None

        if peak_synth is not None:
            final_pred = "synthetic" if peak_synth >= 0.50 else "real"
            final_risk = "high" if peak_synth >= 0.70 else ("medium" if peak_synth >= 0.50 else "low")
            final_action = "block" if final_risk == "high" else ("verify" if final_risk == "medium" else "allow")
        else:
            final_pred = "unknown"
            final_risk = "not_assessed"
            final_action = "not_evaluated"

        return {
            "type": "session_summary",
            "total_duration_seconds": round(len(self.pcm_buffer) / self.sample_rate, 2),
            "windows_analyzed": self.window_index,
            "peak_synthetic_probability": peak_synth,
            "final_prediction": final_pred,
            "final_risk_level": final_risk,
            "final_action": final_action,
            "model_version": settings.MOCK_MODEL_VERSION if self.engine_type == "mock" else "aasist-v1",
        }

    def cleanup(self) -> None:
        """Release in-memory audio buffers on disconnect."""
        self.pcm_buffer = np.zeros(0, dtype=np.float32)
        self.raw_bytes_buffer.clear()
        self._is_cleaned_up = True
