"""
Speaker Verification & Human Impersonation Detection Engine.

Extracts biometric acoustic embeddings from reference audio and compares
incoming call audio against enrolled speaker profiles using cosine distance.

Explicitly addresses human impersonation attacks that acoustic anti-spoofing
(AASIST) alone cannot detect.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List, Union
import numpy as np

from app.ml.audio_decoder import decode_audio
from app.ml.features import AudioFeatureExtractor
from app.schemas.speaker_verification import (
    VerificationStateEnum,
    SpeakerEnrollmentResponse,
    SpeakerVerificationResponse,
    EnrolledSpeakerDTO,
)

logger = logging.getLogger(__name__)

DEFAULT_STORE_PATH = Path(__file__).resolve().parent.parent.parent / "ml_data" / "enrolled_speakers.json"

# Experimental legacy thresholds; no held-out identity calibration evidence.
MATCH_THRESHOLD = 0.75
MISMATCH_THRESHOLD = 0.50
MIN_AUDIO_DURATION_SEC = 1.0


class SpeakerStore:
    """
    Persistent store for speaker voice embeddings.
    """

    def __init__(self, store_path: Path = DEFAULT_STORE_PATH):
        self.store_path = store_path
        self._speakers: Dict[str, Dict[str, Any]] = {}
        self._load()

    def _load(self):
        if self.store_path.exists():
            try:
                with open(self.store_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._speakers = data.get("speakers", {})
                logger.info("Loaded %d enrolled speakers from %s", len(self._speakers), self.store_path)
            except Exception as e:
                logger.warning("Failed to load speaker store (%s); starting with empty store.", e)
                self._speakers = {}
        else:
            self._speakers = {}

    def _save(self):
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(self.store_path, "w", encoding="utf-8") as f:
                json.dump({"speakers": self._speakers, "updated_at": datetime.utcnow().isoformat()}, f, indent=2)
        except Exception as e:
            logger.error("Failed to save speaker store: %s", e)

    def add(
        self,
        speaker_id: str,
        speaker_name: str,
        embedding: np.ndarray,
        duration_sec: float,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        record = {
            "speaker_id": speaker_id,
            "speaker_name": speaker_name,
            "embedding": embedding.tolist(),
            "embedding_dim": len(embedding),
            "enrolled_at": datetime.utcnow().isoformat(),
            "duration_seconds": round(duration_sec, 2),
            "metadata": metadata or {},
        }
        self._speakers[speaker_id] = record
        self._save()
        return record

    def get(self, speaker_id: str) -> Optional[Dict[str, Any]]:
        self._load()
        return self._speakers.get(speaker_id)

    def list_all(self) -> List[EnrolledSpeakerDTO]:
        self._load()
        result = []
        for s_id, s_data in self._speakers.items():
            result.append(
                EnrolledSpeakerDTO(
                    speaker_id=s_id,
                    speaker_name=s_data.get("speaker_name", s_id),
                    enrolled_at=s_data.get("enrolled_at", ""),
                    duration_seconds=s_data.get("duration_seconds", 0.0),
                    sample_count=1,
                )
            )
        return result

    def delete(self, speaker_id: str) -> bool:
        if speaker_id in self._speakers:
            del self._speakers[speaker_id]
            self._save()
            return True
        return False


class SpeakerVerificationService:
    """
    Biometric Speaker Verification Service.
    """

    def __init__(self, store_path: Optional[Path] = None):
        self.store = SpeakerStore(store_path or DEFAULT_STORE_PATH)
        self.feature_extractor = AudioFeatureExtractor()

    def _extract_embedding(self, waveform: np.ndarray, sr: int = 16000) -> np.ndarray:
        """
        Extract a normalized MFCC descriptor (not a trained speaker embedding).
        Uses MFCC filterbank coefficients (c1..c12) and dynamic spectral statistics,
        excluding energy offset (c0) to ensure gain-invariance.
        """
        features = self.feature_extractor.extract_features(waveform, sr)
        # Extract c1..c12 means (indices 2 to 26 step 2)
        mfcc_means = features[2:26:2]
        # Extract c1..c12 stds (indices 3 to 26 step 2)
        mfcc_stds = features[3:26:2]
        # Extract deltas means
        delta_means = features[28:52:2]

        # Combine vocal tract filter shape and dynamics (36 dimensions)
        vocal_tract_emb = np.concatenate([mfcc_means, mfcc_stds, delta_means])
        norm = np.linalg.norm(vocal_tract_emb)
        if norm > 1e-6:
            vocal_tract_emb = vocal_tract_emb / norm
        return vocal_tract_emb.astype(np.float32)

    def enroll(
        self,
        speaker_id: str,
        speaker_name: str,
        audio_source: Union[bytes, np.ndarray, str, Path],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SpeakerEnrollmentResponse:
        """
        Enroll a speaker profile from reference voice audio.
        """
        waveform, sr = decode_audio(audio_source, target_sr=16000, mono=True)
        duration_sec = len(waveform) / 16000.0

        if duration_sec < MIN_AUDIO_DURATION_SEC:
            raise ValueError(
                f"Audio too short for enrollment ({duration_sec:.2f}s). Minimum {MIN_AUDIO_DURATION_SEC}s required."
            )

        embedding = self._extract_embedding(waveform, sr)
        record = self.store.add(
            speaker_id=speaker_id,
            speaker_name=speaker_name,
            embedding=embedding,
            duration_sec=duration_sec,
            metadata=metadata,
        )

        return SpeakerEnrollmentResponse(
            speaker_id=speaker_id,
            speaker_name=speaker_name,
            embedding_dim=len(embedding),
            duration_seconds=round(duration_sec, 2),
            status="ENROLLED",
            metadata=metadata or {},
        )

    def verify(
        self,
        speaker_id: str,
        audio_source: Union[bytes, np.ndarray, str, Path],
    ) -> SpeakerVerificationResponse:
        """
        Verify incoming voice audio against an enrolled speaker profile.
        """
        record = self.store.get(speaker_id)
        if not record:
            return SpeakerVerificationResponse(
                speaker_id=speaker_id,
                state=VerificationStateEnum.NOT_ENROLLED,
                similarity_score=None,
                explanation=f"Speaker ID '{speaker_id}' is not enrolled in the reference identity registry.",
                duration_seconds=0.0,
            )

        waveform, sr = decode_audio(audio_source, target_sr=16000, mono=True)
        duration_sec = round(len(waveform) / 16000.0, 2)

        if duration_sec < MIN_AUDIO_DURATION_SEC or np.max(np.abs(waveform)) < 0.005:
            return SpeakerVerificationResponse(
                speaker_id=speaker_id,
                state=VerificationStateEnum.INSUFFICIENT_AUDIO,
                similarity_score=None,
                explanation=f"Audio duration ({duration_sec}s) or vocal energy is insufficient for reliable biometric verification.",
                duration_seconds=duration_sec,
            )

        test_embedding = self._extract_embedding(waveform, sr)
        ref_embedding = np.array(record["embedding"], dtype=np.float32)

        # Compute cosine similarity
        ref_norm = np.linalg.norm(ref_embedding)
        test_norm = np.linalg.norm(test_embedding)
        if ref_norm > 1e-6 and test_norm > 1e-6:
            similarity = float(np.dot(test_embedding, ref_embedding) / (ref_norm * test_norm))
        else:
            similarity = 0.0

        # Experimental thresholding; this MFCC comparison is not validated identity authentication.
        if similarity >= MATCH_THRESHOLD:
            state = VerificationStateEnum.IDENTITY_MATCH
            explanation = (
                f"Vocal characteristics match enrolled profile for '{record['speaker_name']}' "
                f"(cosine similarity: {similarity:.3f} >= {MATCH_THRESHOLD})."
            )
        elif similarity <= MISMATCH_THRESHOLD:
            state = VerificationStateEnum.IDENTITY_MISMATCH
            explanation = (
                f"Vocal characteristics significantly diverge from enrolled profile for '{record['speaker_name']}' "
                f"(cosine similarity: {similarity:.3f} <= {MISMATCH_THRESHOLD}). Possible human impersonation."
            )
        else:
            state = VerificationStateEnum.IDENTITY_UNCERTAIN
            explanation = (
                f"Vocal similarity ({similarity:.3f}) falls in the ambiguous zone ({MISMATCH_THRESHOLD} - {MATCH_THRESHOLD}). "
                "Identity cannot be definitively verified."
            )

        return SpeakerVerificationResponse(
            speaker_id=speaker_id,
            state=state,
            similarity_score=round(similarity, 4),
            thresholds={"match_threshold": MATCH_THRESHOLD, "mismatch_threshold": MISMATCH_THRESHOLD},
            explanation=explanation,
            duration_seconds=duration_sec,
        )

    def list_speakers(self) -> List[EnrolledSpeakerDTO]:
        return self.store.list_all()

    def delete_speaker(self, speaker_id: str) -> bool:
        return self.store.delete(speaker_id)


# Global singleton instance
_speaker_service_instance: Optional[SpeakerVerificationService] = None


def get_speaker_verification_service() -> SpeakerVerificationService:
    global _speaker_service_instance
    if _speaker_service_instance is None:
        _speaker_service_instance = SpeakerVerificationService()
    return _speaker_service_instance
