import asyncio
import hashlib
import time
from pathlib import Path
from typing import Optional, Dict, Any
from app.config import settings
from app.schemas.detection import (
    DetectionResultDTO,
    PredictionEnum,
    RiskLevelEnum,
)
from app.services.detection.base import BaseDetectionService


class MockDetectionService(BaseDetectionService):
    """
    Mock Voice Cloning Detection Service.
    
    Simulates acoustic analysis, neural vocoder anomaly detection, phase discontinuity checks,
    and background spectral coherence.
    
    Provides deterministic yet realistic probabilistic results based on file contents,
    with an extensible structure ready to be swapped with the real ML pipeline.
    """

    def __init__(self, model_version: str = "mock-v1"):
        self.model_version = model_version

    def get_model_info(self) -> Dict[str, Any]:
        return {
            "name": "SIH26104-MockVoiceForensics",
            "version": self.model_version,
            "type": "heuristic_spectral_mock",
            "supported_formats": settings.ALLOWED_EXTENSIONS,
            "sample_rate_target_hz": 16000,
            "status": "ready"
        }

    async def detect(
        self,
        audio_path: Path,
        filename: str,
        mime_type: str,
        file_size_bytes: int,
        duration_seconds: Optional[float] = None,
        extra_metadata: Optional[Dict[str, Any]] = None,
    ) -> DetectionResultDTO:
        start_time = time.perf_counter()
        
        # Simulate realistic model latency (e.g. 150ms - 300ms)
        await asyncio.sleep(0.18)

        # Generate deterministic seed from file content hash or name
        hash_seed = 0
        try:
            if audio_path.exists():
                with open(audio_path, "rb") as f:
                    chunk = f.read(8192)
                    hash_seed = int(hashlib.sha256(chunk).hexdigest()[:8], 16)
        except Exception:
            hash_seed = int(hashlib.sha256(filename.encode()).hexdigest()[:8], 16)

        # Determine prediction category based on heuristics and filename hints (useful for testing)
        fn_lower = filename.lower()
        if "fake" in fn_lower or "clone" in fn_lower or "synthetic" in fn_lower or "ai" in fn_lower:
            prediction = PredictionEnum.SYNTHETIC
            confidence = 0.92 + (hash_seed % 70) / 1000.0  # 0.92 - 0.989
            risk_level = RiskLevelEnum.HIGH
            attack_type = "Neural Voice Conversion (Diffusion Vocoder)"
            explanation = (
                "Acoustic analysis revealed anomalous high-frequency harmonic phase discontinuities "
                "characteristic of synthetic neural vocoder generation. Biometric pitch jitter also "
                "lacked organic glottal micro-tremor."
            )
            spectral_artifacts = {
                "phase_coherence_anomaly": 0.88,
                "vocoder_footprint_score": 0.94,
                "glottal_pulse_jitter_variance": 0.04,
                "spectral_centroid_shift_hz": 420.5
            }
        elif "replay" in fn_lower or "speaker" in fn_lower:
            prediction = PredictionEnum.REPLAY
            confidence = 0.85 + (hash_seed % 100) / 1000.0
            risk_level = RiskLevelEnum.MEDIUM
            attack_type = "Acoustic Room Impulse / Physical Speaker Replay"
            explanation = (
                "Reverberant convolution artifacts and secondary microphone coloration detected. "
                "Signal indicates replay attack through electroacoustic transducer."
            )
            spectral_artifacts = {
                "room_impulse_response_match": 0.82,
                "transducer_distortion_thd": 0.74,
                "subharmonic_resonance_score": 0.69
            }
        elif "real" in fn_lower or "human" in fn_lower or "genuine" in fn_lower:
            prediction = PredictionEnum.REAL
            confidence = 0.91 + (hash_seed % 80) / 1000.0
            risk_level = RiskLevelEnum.LOW
            attack_type = "None (Organic Human Speech)"
            explanation = (
                "Natural biological formant transitions, realistic breath pauses, and organic "
                "frequency modulation consistent with authentic human vocal tract kinematics."
            )
            spectral_artifacts = {
                "organic_glottal_variation": 0.95,
                "ambient_coherence": 0.91,
                "neural_vocoder_presence": 0.03
            }
        else:
            # Deterministic pseudo-random distribution based on hash_seed
            mod = hash_seed % 100
            if mod < 45:
                prediction = PredictionEnum.SYNTHETIC
                confidence = 0.87 + (mod % 10) / 100.0
                risk_level = RiskLevelEnum.HIGH
                attack_type = "Zero-Shot Voice Cloning (Cross-Lingual Diffusion)"
                explanation = (
                    "High-confidence synthetic audio artifact detected across upper formant bands. "
                    "Unnatural pitch prosody contours detected."
                )
                spectral_artifacts = {
                    "phase_coherence_anomaly": 0.86,
                    "vocoder_footprint_score": 0.91,
                    "spectral_centroid_shift_hz": 395.2
                }
            elif mod < 75:
                prediction = PredictionEnum.REAL
                confidence = 0.89 + (mod % 10) / 100.0
                risk_level = RiskLevelEnum.LOW
                attack_type = "None (Organic Human Speech)"
                explanation = (
                    "Vocal tract resonance dynamics match authentic human physiological baseline. "
                    "No synthetic spectral markers found."
                )
                spectral_artifacts = {
                    "organic_glottal_variation": 0.94,
                    "ambient_coherence": 0.89,
                    "neural_vocoder_presence": 0.04
                }
            elif mod < 92:
                prediction = PredictionEnum.REPLAY
                confidence = 0.81 + (mod % 10) / 100.0
                risk_level = RiskLevelEnum.MEDIUM
                attack_type = "Physical Loudspeaker Acoustic Replay"
                explanation = (
                    "Multi-path acoustic reflections and secondary transducer distortion detected."
                )
                spectral_artifacts = {
                    "room_impulse_response_match": 0.79,
                    "transducer_distortion_thd": 0.68
                }
            else:
                prediction = PredictionEnum.UNKNOWN
                confidence = 0.52 + (mod % 8) / 100.0
                risk_level = RiskLevelEnum.MEDIUM
                attack_type = "Inconclusive / High Ambient Noise"
                explanation = (
                    "Audio sample SNR is low or sample length is insufficient for definitive "
                    "forensic biometric confidence."
                )
                spectral_artifacts = {
                    "snr_db": 12.4,
                    "spectral_entropy": 0.78
                }

        end_time = time.perf_counter()
        processing_time_ms = int((end_time - start_time) * 1000)

        # Compute explicit synthetic probability for mock service
        if prediction == PredictionEnum.SYNTHETIC:
            synth_prob = confidence
        elif prediction == PredictionEnum.REAL:
            synth_prob = 1.0 - confidence
        elif prediction == PredictionEnum.REPLAY:
            synth_prob = confidence
        else:
            synth_prob = 0.50

        # Extensible metadata for future features
        forensic_metadata = {
            "engine_type": "mock",
            "synthetic_probability": round(synth_prob, 4),
            "real_probability": round(1.0 - synth_prob, 4),
            "file_size_bytes": file_size_bytes,
            "detected_mime_type": mime_type,
            "duration_seconds": duration_seconds,
            "extracted_features": {
                "estimated_sample_rate": 44100,
                "channels": 1,
                "dynamic_range_db": 48.2
            },
            "defense_action": "ALLOW" if risk_level == RiskLevelEnum.LOW else "ALERT_AND_QUARANTINE" if risk_level == RiskLevelEnum.HIGH else "FLAG_FOR_REVIEW"
        }

        return DetectionResultDTO(
            engine_type="mock",
            prediction=prediction,
            confidence=round(confidence, 4),
            risk_level=risk_level,
            model_version=self.model_version,
            processing_time_ms=processing_time_ms,
            attack_type=attack_type,
            explanation=explanation,
            spectral_artifacts=spectral_artifacts,
            metadata_json=forensic_metadata,
        )
